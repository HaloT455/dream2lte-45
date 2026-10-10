#!/usr/bin/env python3
"""Extract local, verified V12R5T Android BOOT ramdisk for future P12 UI8 port.

Does NOT change images or partitions; does NOT contact GitHub or upload ROM
files. The extracted ramdisk is *not* added to CI and never published.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

STOCK_SHA = "76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823"
STOCK_SIZE = 40 * 1024 * 1024

def aligned(n, a):
    return ((n+a-1)//a)*a

def kind(b):
    if b.startswith(b"\x1f\x8b"): return "gzip"
    if b.startswith(b"\x04\x22\x4d\x18"): return "lz4-frame"
    if b.startswith(b"\x02\x21\x4c\x18"): return "lz4-legacy"
    if b.startswith(b"\xfd7zXZ\x00"): return "xz"
    if b.startswith(b"070701") or b.startswith(b"070702"): return "cpio-newc"
    return "UNKNOWN"

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot",type=Path,required=True,help="LOCAL original V12R5T BOOT .img")
    p.add_argument("--out",type=Path,required=True,help="LOCAL directory; no upload")
    p.add_argument("--expected-sha256",default=STOCK_SHA)
    args=p.parse_args()
    data=args.boot.read_bytes()
    sha=hashlib.sha256(data).hexdigest()
    if len(data)!=STOCK_SIZE or sha!=args.expected_sha256:
        raise SystemExit("REFUSED: original verified V12R5T BOOT size/hash mismatch")
    if data[:8] != b"ANDROID!":
        raise SystemExit("REFUSED: Android legacy BOOT header missing")
    ksize,ramdisk_size,second_size,page=struct.unpack_from("<IIII",data,8)[0],struct.unpack_from("<I",data,16)[0],struct.unpack_from("<I",data,24)[0],struct.unpack_from("<I",data,36)[0]
    if page not in (2048,4096,8192,16384) or ksize<=0 or ramdisk_size<=0:
        raise SystemExit("REFUSED: Invalid BOOT page/kernel/ramdisk size")
    offset=page+aligned(ksize,page)
    if offset+ramdisk_size>len(data):
        raise SystemExit("REFUSED: ramdisk outside BOOT partition")
    initramfs=data[offset:offset+ramdisk_size]
    format_name=kind(initramfs)
    if format_name=="UNKNOWN":
        raise SystemExit("REFUSED: unsupported ramdisk compression; inspect manually")
    # Reports content-type only; no OEM ramdisk is committed to public GitHub.
    args.out.mkdir(parents=True,exist_ok=True)
    dest=args.out/"V12R5T-UI8-original-ramdisk.bin"
    dest.write_bytes(initramfs)
    report={
        "boot_sha256":sha, "boot_bytes":len(data),
        "ramdisk_offset":offset, "ramdisk_bytes":ramdisk_size,
        "ramdisk_compression":format_name,
        "ramdisk_sha256":hashlib.sha256(initramfs).hexdigest(),
        "warning":"Kernel 5.10 cannot boot One UI 8 merely by replacing /init; UFS + power + vendor HAL port required.",
        "privacy":"Ramdisk extracted on local machine only. Never auto-upload to public GitHub."
    }
    (args.out/"V12R5T-UI8-ramdisk-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    print("READ-ONLY EXTRACTION COMPLETE. NO BOOT IMAGE PATCHED OR FLASHED.")
if __name__=="__main__":
    main()
