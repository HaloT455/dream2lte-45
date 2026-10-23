#!/usr/bin/env python3
"""Host regression: R16 repacker rejects an old interactive/HMP/DH2 ramdisk."""
import gzip
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPACK = ROOT / "scripts/repack_boot_v0.py"
PAGE = 2048

def padded(data):
    return data + bytes((-len(data)) % PAGE)

def fixture(folder, script):
    ramdisk = gzip.compress(script)
    oldkernel = b"reference-kernel"
    dt = b"fdt-test"
    head = bytearray(PAGE)
    head[:8] = b"ANDROID!"
    fields = [len(oldkernel), 0x10008000, len(ramdisk), 0x11000000, 0, 0,
              0x10000100, PAGE, len(dt), 0]
    struct.pack_into("<10I", head, 8, *fields)
    boot = head + padded(oldkernel) + padded(ramdisk) + padded(dt)
    base = folder / "reference.img"
    base.write_bytes(boot)
    return base, dt

def check(legacy):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        body = b"070701" + (b"dh2_fastlane interactive/hispeed_freq" if legacy else b"safe-r16-policy")
        base, dt = fixture(root, body)
        kernel = root / "Image"
        kernel.write_bytes(b"Linux version 4.4.302-Alice-V12R69-R16-ENERGYSTEP")
        devtree = root / "dtb.img"
        devtree.write_bytes(dt)
        out = root / "repacked.img"
        p = subprocess.run(
            [sys.executable, str(REPACK), "--base", str(base), "--kernel",
             str(kernel), "--dt", str(devtree), "--output", str(out)],
            capture_output=True, text=True)
        if legacy:
            assert p.returncode != 0 and "legacy DH2/HMP" in (p.stderr + p.stdout), (p.returncode, p.stderr)
            assert not out.exists(), "dangerous legacy EnergyStep boot must not be published"
        else:
            assert p.returncode == 0 and out.is_file(), (p.returncode, p.stderr)

if __name__ == "__main__":
    check(True)
    check(False)
    print("PASS: obsolete DH2/HMP rejected; safe base accepted; no on-device boot claim")
