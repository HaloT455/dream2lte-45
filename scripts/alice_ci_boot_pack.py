#!/usr/bin/env python3
"""Reassemble exact ALice Exynos8895 boot.img using original user's ramdisk."""
import argparse
import hashlib
import struct
from pathlib import Path

RAMDISK_SHA = "0acad424dbd7eb133c8d315fad4e112a3cc1fb8991b5dafcf2949092035466a2"
TEST_BOOT_SHA = "4173a9b5b4c497070369913369ceabb5682457194343d0e02409f63dc3a3fa08"

def align(n, page):
    return (n + page - 1) // page * page

def pack(kernel, ramdisk, dtb):
    if kernel[56:60] != b"ARM\x64":
        raise ValueError("Bad ARM64 Image")
    if dtb[:4] != b"DTBH" or len(dtb) != 229376:
        raise ValueError("Bad Samsung DTB")
    if hashlib.sha256(ramdisk).hexdigest() != RAMDISK_SHA:
        raise ValueError("NOT the matching original ALice ramdisk; refusing")
    page = 2048
    header = bytearray(page)
    header[:8] = b"ANDROID!"
    struct.pack_into("<10I", header, 8, len(kernel), 0x10008000,
        len(ramdisk), 0x11000000, 0, 0x10f00000,
        0x10000100, page, len(dtb), 0x1a0001a5)
    board = b"SRPPK02A007KU"
    header[48:48+len(board)] = board
    cmdline = b"androidboot.hardware=samsungexynos8895"
    header[64:64+len(cmdline)] = cmdline
    sha = hashlib.sha1()
    for chunk in (kernel, ramdisk, b"", dtb):
        sha.update(chunk)
        sha.update(struct.pack("<I", len(chunk)))
    header[576:608] = sha.digest() + bytes(12)
    out = bytes(header)
    for chunk in (kernel, ramdisk, b"", dtb):
        out += chunk + bytes(align(len(chunk), page) - len(chunk))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, required=True)
    ap.add_argument("--ramdisk", type=Path, required=True)
    ap.add_argument("--dtb", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    binary = pack(args.image.read_bytes(), args.ramdisk.read_bytes(),
                  args.dtb.read_bytes())
    actual = hashlib.sha256(binary).hexdigest()
    if actual != TEST_BOOT_SHA:
        raise ValueError("Final boot differs from locally validated CI repack: " + actual)
    args.out.write_bytes(binary)
    print("VERIFIED boot.img SHA256:", actual)
    print("Bytes:", len(binary))

if __name__ == "__main__":
    main()
