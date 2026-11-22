#!/usr/bin/env python3
"""Repack a Samsung Exynos8895 Android boot v0 image using a newly built kernel.

Requires a REAL, user-supplied original boot image from the target device.
Preserves the original boot header, ramdisk, second-stage and Samsung footer.
Never fabricates missing boot metadata or produces an output from a kernel
Image alone. This repacker does not sign boot images.
"""
import argparse
import hashlib
import struct
from pathlib import Path

MAGIC = b"ANDROID!"
ARM64_MAGIC = b"ARM\x64"
SAMSUNG_DTB_MAGIC = b"DTBH"
SAMSUNG_FOOTER = b"SEANDROIDENFORCE"
HEADER_BYTES = 1632


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def align(value, page):
    return (value + page - 1) // page * page


def fail(message):
    raise ValueError(message)


def unpack_original(original):
    if len(original) < HEADER_BYTES or original[:8] != MAGIC:
        fail("Not a legacy Android boot image (ANDROID! header missing)")
    (kernel_len, kernel_addr, ramdisk_len, ramdisk_addr,
     second_len, second_addr, tags_addr, page, dt_len,
     os_version) = struct.unpack_from("<10I", original, 8)

    if page not in (2048, 4096, 8192, 16384):
        fail("Unsupported boot page size: %s" % page)
    if not kernel_len or not ramdisk_len or not dt_len:
        fail("Missing original kernel, ramdisk, or Samsung DTB: cannot repack safely")

    kernel_pos = page
    ramdisk_pos = align(kernel_pos + kernel_len, page)
    second_pos = align(ramdisk_pos + ramdisk_len, page)
    dt_pos = align(second_pos + second_len, page)
    end = align(dt_pos + dt_len, page)
    if end > len(original):
        fail("Truncated source boot image")

    original_dt = original[dt_pos:dt_pos + dt_len]
    if original_dt[:4] != SAMSUNG_DTB_MAGIC:
        fail("Original boot DTB is not the expected Samsung DTBH format")

    footer = original[end:]
    if footer and not (footer.startswith(SAMSUNG_FOOTER) or
                       not footer.strip(b"\x00")):
        fail("Unknown original boot footer; refusing to discard/forge signatures")
    # A signature is NOT valid after modifying the boot image. The Samsung
    # SEANDROIDENFORCE compatibility trailer is *not* a cryptographic signature.
    return {
        "header": original[:page],
        "ramdisk": original[ramdisk_pos:ramdisk_pos + ramdisk_len],
        "second": original[second_pos:second_pos + second_len],
        "footer": footer,
        "page": page,
        "kernel_address": kernel_addr,
        "ramdisk_address": ramdisk_addr,
        "second_address": second_addr,
        "tags_address": tags_addr,
        "os_version": os_version,
    }


def repack(original, kernel, dtb):
    legacy = unpack_original(original)
    if len(kernel) < 64 or kernel[56:60] != ARM64_MAGIC:
        fail("Newly built Image is not an ARM64 Linux kernel image")
    if dtb[:4] != SAMSUNG_DTB_MAGIC or len(dtb) < 16:
        fail("Newly built DTB is not a Samsung DTBH bundle")

    page = legacy["page"]
    ramdisk = legacy["ramdisk"]
    second = legacy["second"]
    header = bytearray(legacy["header"])
    struct.pack_into("<I", header, 8, len(kernel))
    struct.pack_into("<I", header, 16, len(ramdisk))
    struct.pack_into("<I", header, 24, len(second))
    struct.pack_into("<I", header, 40, len(dtb))

    sha = hashlib.sha1()
    for chunk in (kernel, ramdisk, second, dtb):
        sha.update(chunk)
        sha.update(struct.pack("<I", len(chunk)))
    header[576:608] = sha.digest() + b"\x00" * 12

    out = bytearray(header)
    for chunk in (kernel, ramdisk, second, dtb):
        out.extend(chunk)
        out.extend(b"\x00" * (align(len(chunk), page) - len(chunk)))
    out.extend(legacy["footer"])

    # Ensure original ramdisk bytes are preserved, not generated or substituted.
    parsed = unpack_original(bytes(out))
    if parsed["ramdisk"] != ramdisk or parsed["second"] != second:
        fail("Repacked boot did not preserve original ramdisk/second-stage")
    return bytes(out), sha256(ramdisk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-boot", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--dtb", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    original = args.original_boot.read_bytes()
    image = args.image.read_bytes()
    dtb = args.dtb.read_bytes()
    boot, ramdisk_hash = repack(original, image, dtb)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(boot)
    print("Source boot SHA256:", sha256(original))
    print("Kernel Image SHA256:", sha256(image))
    print("Samsung DTB SHA256:", sha256(dtb))
    print("Preserved original ramdisk SHA256:", ramdisk_hash)
    print("New boot.img SHA256:", sha256(boot))
    print("New boot.img bytes:", len(boot))
    print("UNTESTED ON DEVICE: keep stock boot backup and working recovery.")


if __name__ == "__main__":
    main()
