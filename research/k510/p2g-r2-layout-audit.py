#!/usr/bin/env python3
"""P2G-R2: fail-closed AArch64 Image relocation / reserved RAM audit.

Compiler-only gate, not hardware validation. All addresses derive from known
Exynos8895 SM-G955F logs and pinned donor uniLoader 8895 configuration.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

RAM = [(0x80000000, 0xBC800000), (0xC0000000, 0x100000000),
       (0x880000000, 0x900000000)]
KERNEL_BASE = 0x98000000
LOADER_BASE = 0x87000000
RAMDISK_BASE = 0x84000000
RAMOOPS_BASE = 0x92000000
# S-Boot additions observed in TWRP's /proc/cmdline. Not proven valid for BOOT.
# Exclude conservatively from allocations rather than claiming definitive size.
EXTRA_RESERVED = [
    ("sboot_ess_debug_guard", 0x91200000, 0x1240000),
    ("sboot_ect_guard", 0xA0000000, 0x19000),
    ("sboot_early_boot_flag", 0x80001000, 0x1000),
    ("ramoops_recovery", RAMOOPS_BASE, 0x8000),
    ("samsung_legacy_reservation", 0xE0000000, 0x1900000),
]

def fail(s):
    raise SystemExit("FAIL-CLOSED: " + s)

def overlaps(a, b):
    return a[1] > b[0] and b[1] > a[0]

def inside_ram(a):
    return any(a[0] >= b and a[1] <= e for b, e in RAM)

def parse_manifest(p):
    items = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 3 or not re.fullmatch(r"0x[0-9a-fA-F]+", fields[1]) or not re.fullmatch(r"0x[0-9a-fA-F]+", fields[2]):
            fail("Invalid reserved-memory manifest: " + line)
        name, base, size = fields
        start, length = int(base, 16), int(size, 16)
        items.append((name, start, start + length))
    if len(items) != 12:
        fail("Expected exactly 12 measured P1D reserved-memory regions")
    return items

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, required=True)
    ap.add_argument("--ramdisk", type=Path, required=True)
    ap.add_argument("--loader", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    raw = args.image.read_bytes()
    if len(raw) < 64 or raw[0x38:0x3C] != b"ARM\x64":
        fail("Invalid ARM64 kernel Image magic")
    text_offset, image_size, flags = struct.unpack_from("<QQQ", raw, 8)
    if flags & 1:
        fail("ARM64 Image requests big-endian")
    if text_offset >= 0x200000:
        fail("ARM64 Image text_offset exceeds 2 MiB")
    load_entry = KERNEL_BASE + text_offset
    if (load_entry - text_offset) % 0x200000:
        fail("Linux arm64 boot protocol 2MiB-aligned base violated")
    # image_size is the span the running kernel may need, and can include BSS.
    # 64MiB conservative floor also guards zero / legacy header image_size.
    runtime_span = max(len(raw), image_size, 0x4000000)
    if runtime_span > 0x8000000:
        fail("Kernel runtime span too large; relocation must be reassessed")
    config = args.config.read_text()
    expected_entry = f"CONFIG_PAYLOAD_ENTRY=0x{load_entry:x}"
    if expected_entry not in config.splitlines():
        fail("Compiled uniLoader config does not use Image text_offset-derived entry")
    for c in ["CONFIG_TEXT_BASE=0x87000000",
              "CONFIG_RAMDISK_ENTRY=0x84000000",
              "CONFIG_SAMSUNG_DREAM2LTE=y",
              "CONFIG_POSITION_INDEPENDENT=y"]:
        if c not in config.splitlines():
            fail("Unexpected loader configuration: " + c)
    loader_len = args.loader.stat().st_size
    ramdisk_len = args.ramdisk.stat().st_size
    if loader_len >= 0x3000000:
        fail("Embedded uniLoader would exceed conservative 48MiB relocation limit")
    ranges = [
        ("loader_relocated_plus_2MiB_bss_guard", LOADER_BASE,
         LOADER_BASE + loader_len + 0x200000),
        ("initramfs", RAMDISK_BASE, RAMDISK_BASE + ramdisk_len),
        ("linux_image_runtime_guard", load_entry,
         load_entry + runtime_span),
    ]
    reserved = parse_manifest(args.manifest)
    reserved += [(name, base, base+size) for name, base, size in EXTRA_RESERVED]
    for name, start, end in ranges:
        if not inside_ram((start, end)):
            fail(f"{name} not inside measured physical RAM: {start:#x}-{end:#x}")
        for reserved_name, rb, re in reserved:
            if overlaps((start, end), (rb, re)):
                fail(f"{name} overlaps {reserved_name}: {start:#x}-{end:#x} vs {rb:#x}-{re:#x}")
    for i, a in enumerate(ranges):
        for b in ranges[i+1:]:
            if overlaps((a[1], a[2]), (b[1], b[2])):
                fail(f"{a[0]} overlaps {b[0]}")
    report = {
        "status": "STATIC_MEMORY_AUDIT_ONLY_NO_BOOT_PROOF",
        "device": "SM-G955F Exynos8895 rev10",
        "raw_image_bytes": len(raw),
        "raw_image_sha256": hashlib.sha256(raw).hexdigest(),
        "image_text_offset": hex(text_offset),
        "image_header_runtime_size": hex(image_size),
        "guarded_kernel_runtime_bytes": runtime_span,
        "kernel_entry": hex(load_entry),
        "kernel_2mb_aligned_base": hex(KERNEL_BASE),
        "ranges": [{"name": name, "start": hex(start), "end_exclusive": hex(end)}
                   for name, start, end in ranges],
        "reserved_checked": [{"name": name, "start": hex(start), "end_exclusive": hex(end)}
                             for name, start, end in reserved],
        "early_console": "NOT VERIFIED",
        "bootloader_handoff": "NOT VERIFIED",
        "note": "Measured reservations from working 4.4 and Recovery, not runtime firmware proof.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("R2: static overlap checks PASS; hardware boot NOT verified")

if __name__ == "__main__":
    main()
