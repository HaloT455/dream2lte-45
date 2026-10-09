#!/usr/bin/env python3
"""K510 P2C: audit structural Android legacy boot report; no boot image produced."""
from __future__ import annotations
import json
import pathlib
import re
import sys

TEXT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                    else pathlib.Path(__file__).with_name("P2C-BOOT-HEADER.txt")).read_text()
NAMES = (
    "kernel_size", "kernel_addr", "ramdisk_size", "ramdisk_addr",
    "second_size", "second_addr", "tags_addr", "page_size",
    "dt_size_or_header_version"
)

def field(name):
    match = re.search(r"(?m)^" + re.escape(name) + r":\s*(0x[0-9a-fA-F]+|[0-9]+)", TEXT)
    if not match:
        raise SystemExit("Missing field: " + name)
    return int(match.group(1), 0)

data = {k: field(k) for k in NAMES}
assert data["kernel_size"] > 0 and data["ramdisk_size"] > 0
page = data["page_size"]
if page not in (2048, 4096, 8192, 16384):
    raise SystemExit("Unexpected legacy page size: " + str(page))
if "Header bytes returned: 4096" not in TEXT:
    raise SystemExit("Expected original READ ONLY 4096-byte header report")
if "Device verified by ro.hardware=samsungexynos8895" not in TEXT:
    raise SystemExit("Not an Exynos8895 source report")
if data["second_size"] != 0:
    raise SystemExit("Second-stage payload requires additional packing review")

# Historical pre-versioned Android boot header v0 used offset 0x28 for dt_size.
# For modern v0+ layouts offset 0x28 can denote header_version instead.
# A 229376 header_version is impossible -> strongest explanation is legacy dt_size.
dt_size = data["dt_size_or_header_version"]
if dt_size <= 2 or dt_size % 4 != 0:
    raise SystemExit("Legacy dt_size hypothesis unproven by this report")

def aligned(n):
    return ((n + page - 1) // page) * page

# Layout if this is the historic legacy header: header + kernel + ramdisk + second + dt.
# No assertion that this equals BOOT partition size (not provided in report).
layout = {
    "format_assumption": "Android legacy pre-versioned boot header with dt_size at 0x28",
    "format_verified_from_full_image": False,
    "device": "Samsung SM-G955F rev05 / Exynos 8895",
    "page_size": page,
    "kernel_size": data["kernel_size"],
    "kernel_addr": hex(data["kernel_addr"]),
    "ramdisk_size": data["ramdisk_size"],
    "ramdisk_addr": hex(data["ramdisk_addr"]),
    "second_size": 0,
    "tags_addr": hex(data["tags_addr"]),
    "dt_size_assumed": dt_size,
    "header_padded_bytes": page,
    "kernel_padded_bytes": aligned(data["kernel_size"]),
    "ramdisk_padded_bytes": aligned(data["ramdisk_size"]),
    "dt_padded_bytes": aligned(dt_size),
}
layout["assumed_min_image_size"] = (page + aligned(data["kernel_size"])
                                    + aligned(data["ramdisk_size"]) + aligned(dt_size))
# Actual physical RAM regions from P1D read-only phone DT, size in bytes.
ram = [(0x80000000, 0x3c800000),
       (0xc0000000, 0x40000000),
       (0x880000000, 0x80000000)]
for label in ("kernel_addr", "ramdisk_addr", "tags_addr"):
    addr = data[label]
    layout[label + "_inside_p1d_ram"] = any(base <= addr < base + size
                                            for base, size in ram)
layout["loader_address_mismatch_warning"] = (
    "Header kernel/ramdisk/tags addresses are outside live P1D RAM ranges. "
    "Do not interpret these as physical 5.10 load addresses without S-Boot "
    "handoff traces, relocation analysis and Samsung packing verification."
)
layout["permitted_next_step"] = "compile-only audit, not boot.img flash"
print(json.dumps(layout, indent=2))
if len(sys.argv) > 2:
    out = pathlib.Path(sys.argv[2])
    out.write_text(json.dumps(layout, indent=2) + "\n")
