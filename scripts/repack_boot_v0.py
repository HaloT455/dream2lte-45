#!/usr/bin/env python3
"""Repack an Android boot image v0 while preserving its ramdisk and footer."""

import argparse
import hashlib
import struct
from pathlib import Path


BOOT_MAGIC = b"ANDROID!"
HEADER_SIZE = 1632
ID_OFFSET = 576
ID_SIZE = 32


def align(value: int, page_size: int) -> int:
    return (value + page_size - 1) // page_size * page_size


def section(image: bytes, offset: int, size: int, page_size: int):
    data = image[offset:offset + size]
    if len(data) != size:
        raise ValueError("truncated boot image payload")
    return data, offset + align(size, page_size)


def padded(data: bytes, page_size: int) -> bytes:
    return data + bytes(align(len(data), page_size) - len(data))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--dt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    image = args.base.read_bytes()
    kernel = args.kernel.read_bytes()
    dt = args.dt.read_bytes()

    if len(image) < HEADER_SIZE or image[:8] != BOOT_MAGIC:
        raise ValueError("base is not an Android boot image v0")

    fields = list(struct.unpack_from("<10I", image, 8))
    old_kernel_size, _, ramdisk_size, _, second_size, _, _, page_size, dt_size, _ = fields
    if page_size < HEADER_SIZE or page_size & (page_size - 1):
        raise ValueError(f"invalid page size: {page_size}")

    offset = page_size
    _, offset = section(image, offset, old_kernel_size, page_size)
    ramdisk, offset = section(image, offset, ramdisk_size, page_size)
    second, offset = section(image, offset, second_size, page_size)
    _, offset = section(image, offset, dt_size, page_size)
    footer = image[offset:]

    fields[0] = len(kernel)
    fields[8] = len(dt)
    first_page = bytearray(image[:page_size])
    struct.pack_into("<10I", first_page, 8, *fields)

    digest = hashlib.sha1()
    for payload in (kernel, ramdisk, second, dt):
        digest.update(payload)
        digest.update(struct.pack("<I", len(payload)))
    first_page[ID_OFFSET:ID_OFFSET + ID_SIZE] = digest.digest() + bytes(12)

    output = b"".join((
        first_page,
        padded(kernel, page_size),
        padded(ramdisk, page_size),
        padded(second, page_size),
        padded(dt, page_size),
        footer,
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)

    print(f"kernel_size={len(kernel)}")
    print(f"ramdisk_size={len(ramdisk)}")
    print(f"second_size={len(second)}")
    print(f"dt_size={len(dt)}")
    print(f"footer_size={len(footer)}")
    print(f"image_id={digest.hexdigest()}")
    print(f"output_size={len(output)}")


if __name__ == "__main__":
    main()
