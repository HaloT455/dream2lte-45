#!/usr/bin/env python3
"""Repack ALICE R16 Image+DTB as SM-G955F Android boot.img for testing.

Requires SHA-pinned owner boot reference. Drops only obsolete DH2/HMP/
interactive init boot policy, retaining Android init, fstab and dpolicy.
AVB is REGENERATED with algorithm NONE; unsigned unlocked-device test ONLY.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile

REFERENCE_SHA = "9012313ab3d8b2e15fe00871da4872d4d09f7068211b36604eede6fe138c646b"
PARTITION_SIZE = 40 * 1024 * 1024
SEANDROID = b"SEANDROIDENFORCE\x00"

def align(n, b):
    return (n + b - 1) // b * b

def sha256(b):
    return hashlib.sha256(b).hexdigest()

def read_boot(data):
    if len(data) != PARTITION_SIZE or data[:8] != b"ANDROID!":
        raise ValueError("Expected 40 MiB Android boot image")
    f = list(struct.unpack_from("<10I", data, 8))
    kernel_size, _, ramdisk_size, _, second_size, _, _, page, dt_size, _ = f
    if page != 2048 or second_size:
        raise ValueError("Unsupported boot layout")
    kp = page
    rp = kp + align(kernel_size, page)
    dp = rp + align(ramdisk_size, page)
    end = dp + align(dt_size, page)
    if data[end:end+16] != b"SEANDROIDENFORCE":
        raise ValueError("Unexpected Samsung boot trailer")
    if data[-64:-60] != b"AVBf":
        raise ValueError("Missing original AVB footer")
    orig, vbmeta, size = struct.unpack_from(">QQQ", data, len(data)-52)
    if not (end <= orig < vbmeta and vbmeta + size < len(data)):
        raise ValueError("Invalid AVB metadata offsets")
    return (data[:page], f, data[kp:kp+kernel_size],
            data[rp:rp+ramdisk_size], data[dp:dp+dt_size])

def read_cpio(b):
    result = []
    p = 0
    for _ in range(10000):
        head = b[p:p+110]
        if len(head) != 110 or head[:6] != b"070701":
            raise ValueError("Only complete newc CPIO is supported")
        v = [int(head[i:i+8], 16) for i in range(6,110,8)]
        size, nsize = v[6], v[11]
        p += 110
        nr = b[p:p+nsize]
        if not nr.endswith(b"\x00"):
            raise ValueError("Bad CPIO pathname")
        name = nr[:-1].decode("utf-8")
        p = align(p + nsize, 4)
        payload = b[p:p+size]
        if len(payload) != size:
            raise ValueError("Truncated CPIO entry")
        p = align(p+size, 4)
        if name == "TRAILER!!!":
            return result
        result.append((name, head, nr, payload))
    raise ValueError("CPIO entry limit exceeded")

def write_cpio(entries):
    out = bytearray()
    seen = set()
    for name, header, nr, data in entries:
        if name in seen:
            raise ValueError("Duplicate CPIO entry")
        seen.add(name)
        head = bytearray(header)
        head[54:62] = ("%08x" % len(data)).encode()
        out += head + nr
        out += bytes((-len(out)) % 4)
        out += data
        out += bytes((-len(out)) % 4)
    trailer = b"TRAILER!!!\x00"
    fields = (0,0,0,0,1,0,0,0,0,0,0,len(trailer),0)
    out += b"070701" + b"".join(("%08x" % i).encode() for i in fields) + trailer
    out += bytes((-len(out)) % 4)
    return bytes(out)

def patch_ramdisk(blob):
    if not blob.startswith(b"\x1f\x8b"):
        raise ValueError("Reference ramdisk is not gzip")
    ents = read_cpio(gzip.decompress(blob))
    names = {n for n, *_ in ents}
    must = {"init","fstab.samsungexynos8895","dpolicy","init.rc",
            "dh2_fastlane_boot.sh","dh2_stage51.sh"}
    if not must.issubset(names):
        raise ValueError("Boot ramdisk differs from owner reference")
    out = []
    for name, header, nr, data in ents:
        if name in ("dh2_fastlane_boot.sh","dh2_stage51.sh"):
            continue
        if name == "init.rc":
            if b"/cpufreq/interactive/" not in data or b"start dh2_fastlane" not in data:
                raise ValueError("Unexpected interactive/DH2 init policy")
            data = b"# ALICE R16: removed obsolete HMP/interactive/DH2 policy.\n"
        out.append((name,header,nr,data))
    packed = write_cpio(out)
    if b"dh2_fastlane" in packed or b"/cpufreq/interactive/" in packed:
        raise ValueError("Legacy boot config still present")
    if not {"init","fstab.samsungexynos8895","dpolicy"}.issubset({x[0] for x in read_cpio(packed)}):
        raise ValueError("Critical boot files lost")
    return gzip.compress(packed, compresslevel=9, mtime=0)

def make_unsigned_test_boot(base, kernel, dt):
    h, fields, _, ramdisk, _ = read_boot(base)
    if b"ENERGYSTEP" not in kernel and b"energy_step" not in kernel:
        raise ValueError("Expected R16 EnergyStep kernel Image")
    if len(kernel) < 4 * 1024 * 1024 or len(dt) < 4096:
        raise ValueError("Unexpected Image/dtb sizes")
    ramdisk = patch_ramdisk(ramdisk)
    fields[0], fields[2], fields[8] = len(kernel), len(ramdisk), len(dt)
    header = bytearray(h)
    struct.pack_into("<10I", header, 8, *fields)
    old_id = hashlib.sha1()
    for part in (kernel,ramdisk,b"",dt):
        old_id.update(part)
        old_id.update(struct.pack("<I",len(part)))
    header[576:608] = old_id.digest() + bytes(12)
    payload = bytearray(header)
    for part in (kernel,ramdisk,dt):
        payload += part
        payload += bytes((-len(part)) % fields[7])
    payload += SEANDROID
    if len(payload) > PARTITION_SIZE - 8192:
        raise ValueError("Payload does not fit 40 MiB boot partition")
    return bytes(payload)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--kernel", required=True, type=Path)
    p.add_argument("--dt", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--avbtool", default="avbtool")
    p.add_argument("--allow-unsigned-test-boot", action="store_true", required=True)
    a = p.parse_args()
    base = a.base.read_bytes()
    if sha256(base) != REFERENCE_SHA:
        p.error("Refused: reference boot SHA256 does not match owner-provided boot.img")
    payload = make_unsigned_test_boot(base, a.kernel.read_bytes(), a.dt.read_bytes())
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "boot.img"
        out.write_bytes(payload)
        subprocess.run([a.avbtool,"add_hash_footer","--image",str(out),
                        "--partition_name","boot","--partition_size",str(PARTITION_SIZE),
                        "--algorithm","NONE"], check=True)
        img = out.read_bytes()
        if len(img) != PARTITION_SIZE or img[-64:-60] != b"AVBf":
            raise ValueError("New AVB footer invalid")
        orig, meta, size = struct.unpack_from(">QQQ",img,len(img)-52)
        if not (orig <= meta < len(img) and img[meta:meta+4] == b"AVB0"
                and meta+size < len(img)):
            raise ValueError("AVB vbmeta offsets invalid")
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_bytes(img)
    print("UNSIGNED UNTESTED boot.img, unlocked test device only")
    print("boot.img",len(img),"bytes, SHA256",sha256(img))
    print("NOT confirmation of SIM2 LTE, dual-LTE or boot compatibility")

if __name__ == "__main__":
    main()
