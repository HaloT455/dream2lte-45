#!/usr/bin/env python3
"""Pack R16 Image+DTBH into owner-confirmed bootable V12R5T Enforcing boot.

The template has boot v0 / page 2048, gzip newc ramdisk with init/dpolicy/
fstab, no AVB footer and no Samsung trailer. Preserve ramdisk bit-for-bit.
NO new AVB footer is introduced. Output is device-UNTESTED.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
from pathlib import Path
import struct

REFERENCE_SHA256 = "80c3f368ac934725aa1bae01529646c339ade3b88b656e4f98670ba71a850043"
REFERENCE_RAMDISK_SHA256 = "0acad424dbd7eb133c8d315fad4e112a3cc1fb8991b5dafcf2949092035466a2"
BOOT_CAP = 40 * 1024 * 1024


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def align(n: int, page: int) -> int:
    return (n + page - 1) // page * page


def unpack(image: bytes, require_reference: bool = True) -> dict:
    if require_reference and sha256(image) != REFERENCE_SHA256:
        raise ValueError("Owner V12R5T boot SHA256 mismatch")
    if len(image) < 2048 or image[:8] != b"ANDROID!":
        raise ValueError("Not a boot-v0 Android boot image")
    fields = list(struct.unpack_from("<10I", image, 8))
    ksize, _, rsize, _, ssize, _, _, page, dsize, _ = fields
    if page != 2048 or ssize or not min(ksize, rsize, dsize):
        raise ValueError("Unexpected reference header layout")
    kp = page
    rp = kp + align(ksize, page)
    dp = rp + align(rsize, page)
    end = dp + align(dsize, page)
    if end != len(image):
        raise ValueError("Unexpected footer/trailer; stop rather than modify boot")
    kernel = image[kp:kp + ksize]
    ramdisk = image[rp:rp + rsize]
    dtb = image[dp:dp + dsize]
    if sha256(ramdisk) != REFERENCE_RAMDISK_SHA256 and require_reference:
        raise ValueError("Unexpected ramdisk")
    if not ramdisk.startswith(bytes([0x1f, 0x8b])):
        raise ValueError("Ramdisk is not gzip")
    cpio = gzip.decompress(ramdisk)
    for token in (b"070701", bytes.fromhex("646f706c69637900"), b"fstab.samsungexynos8895", b"init"+bytes([0])):
        if token not in cpio:
            raise ValueError("Ramdisk missing required boot component")
    h = hashlib.sha1()
    for part in (kernel, ramdisk, b"", dtb):
        h.update(part)
        h.update(struct.pack("<I", len(part)))
    if h.digest() != image[576:596]:
        raise ValueError("Android boot SHA1 header ID invalid")
    return {"header": image[:page], "fields": fields, "kernel": kernel,
            "ramdisk": ramdisk, "dtb": dtb, "page": page}


def repack(base: bytes, kernel: bytes, dtb: bytes, *, selftest=False) -> bytes:
    b = unpack(base)
    if not selftest and not (b"-R16-" in kernel and b"ENERGYSTEP" in kernel):
        raise ValueError("Not a compiled ALICE R16 EnergyStep kernel Image")
    if not 4 * 1024 * 1024 <= len(kernel) <= BOOT_CAP:
        raise ValueError("Kernel Image size implausible")
    if not dtb.startswith(b"DTBH") or len(dtb) < 4096:
        raise ValueError("Expected compiled Samsung DTBH dtb.img")
    header = bytearray(b["header"])
    fields = b["fields"]
    fields[0] = len(kernel)
    fields[2] = len(b["ramdisk"])
    fields[8] = len(dtb)
    struct.pack_into("<10I", header, 8, *fields)
    h = hashlib.sha1()
    for part in (kernel, b["ramdisk"], b"", dtb):
        h.update(part)
        h.update(struct.pack("<I", len(part)))
    header[576:608] = h.digest() + bytes(12)
    output = bytearray(header)
    for part in (kernel, b["ramdisk"], dtb):
        output.extend(part)
        output.extend(bytes(align(len(part), b["page"]) - len(part)))
    if len(output) > BOOT_CAP:
        raise ValueError("Repacked boot.img would exceed conservative 40 MiB partition cap")
    checked = unpack(bytes(output), require_reference=False)
    if (checked["ramdisk"] != b["ramdisk"] or
        checked["kernel"] != kernel or checked["dtb"] != dtb or
        checked["header"][64:576] != b["header"][64:576]):
        raise ValueError("Boot roundtrip validation failed")
    return bytes(output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--kernel", type=Path)
    p.add_argument("--dt", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()
    base = args.base.read_bytes()
    if args.selftest:
        b = unpack(base)
        result = repack(base, b["kernel"], b["dtb"], selftest=True)
        if result != base:
            p.error("Template byte-for-byte reproducibility failed")
        print("PASS: V12R5T known-working boot roundtrips byte-for-byte")
        return
    if not (args.kernel and args.dt and args.output):
        p.error("--kernel, --dt and --output needed to pack R16")
    out = repack(base, args.kernel.read_bytes(), args.dt.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out)
    print("WROTE", args.output, len(out), "SHA256", sha256(out))
    print("STATUS: boot-v0 structure verified; physical boot, SIM and camera UNTESTED")


if __name__ == "__main__":
    main()
