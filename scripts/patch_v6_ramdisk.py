#!/usr/bin/env python3
"""Patch the V6 newc ramdisk for 3.2-GiB LZ4 ZRAM and optional F2FS cache."""

import argparse
import gzip
import io
from pathlib import Path


TARGET = "fstab.samsungexynos8895"
OLD_ZRAM = (
    b"/dev/block/zram0\tnone\t\tswap\tdefaults\t"
    b"zramsize=2684354560,max_comp_streams=8"
)
NEW_ZRAM = (
    b"/dev/block/zram0\tnone\t\tswap\tdefaults\t"
    b"zramsize=3435970560,max_comp_streams=4"
)
CACHE_DEVICE = b"/dev/block/platform/11120000.ufs/by-name/CACHE"
CACHE_F2FS = (
    CACHE_DEVICE
    + b"\t/cache\t    f2fs\tnoatime,nosuid,nodev,discard,background_gc=on"
      b"\twait,check,formattable\n"
)


def align4(value):
    return (value + 3) & ~3


def patch_fstab(data):
    if data.count(OLD_ZRAM) != 1:
        raise ValueError("expected exactly one V6 ZRAM entry")
    data = data.replace(OLD_ZRAM, NEW_ZRAM)

    if CACHE_F2FS not in data:
        lines = data.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if CACHE_DEVICE in line and b"/cache" in line and b"ext4" in line:
                lines.insert(index + 1, CACHE_F2FS)
                break
        else:
            raise ValueError("V6 ext4 cache entry was not found")
        data = b"".join(lines)

    return data


def patch_newc(archive):
    output = bytearray()
    offset = 0
    patched = False

    while offset + 110 <= len(archive):
        header = archive[offset:offset + 110]
        magic = header[:6]
        if magic not in (b"070701", b"070702"):
            raise ValueError("ramdisk is not a newc archive")

        fields = [
            int(header[6 + field * 8:14 + field * 8], 16)
            for field in range(13)
        ]
        file_size = fields[6]
        name_size = fields[11]
        name_end = offset + 110 + name_size
        name_raw = archive[offset + 110:name_end]
        name = name_raw[:-1].decode("utf-8")
        data_offset = align4(name_end)
        data = archive[data_offset:data_offset + file_size]
        next_offset = align4(data_offset + file_size)

        if len(data) != file_size:
            raise ValueError("truncated newc entry")
        if name == TARGET:
            data = patch_fstab(data)
            fields[6] = len(data)
            if magic == b"070702":
                fields[12] = sum(data) & 0xFFFFFFFF
            patched = True

        new_header = magic + b"".join(f"{value:08x}".encode() for value in fields)
        output.extend(new_header)
        output.extend(name_raw)
        output.extend(bytes(align4(len(output)) - len(output)))
        output.extend(data)
        output.extend(bytes(align4(len(output)) - len(output)))
        offset = next_offset

        if name == "TRAILER!!!":
            output.extend(archive[offset:])
            break

    if not patched:
        raise ValueError(f"{TARGET} was not found")
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    archive = gzip.decompress(args.input.read_bytes())
    patched = patch_newc(archive)

    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", compresslevel=9, mtime=0) as stream:
        stream.write(patched)
    args.output.write_bytes(compressed.getvalue())


if __name__ == "__main__":
    main()
