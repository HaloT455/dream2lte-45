#!/usr/bin/env python3
"""Verify the opt-in Aura Android13 fstab was preserved verbatim.

Only analyses the ROM profile; never rewrites the built-in boot ramdisk.
"""
from hashlib import sha1, sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "alice/rom-profiles/aura-android13-erofs/fstab.samsungexynos8895"
data = PROFILE.read_bytes()
assert len(data) == 2409, "donor fstab unexpectedly changed"
assert sha256(data).hexdigest() == (
    "6dcd1280873f6628f8d4392c2679f42bec170ec85f849c3f16b302fd257c8d60"
)
assert sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == (
    "d1dae668dd63283d86c63fc76c2203c519af6bdb"
)
entries = [line.split() for line in data.decode("ascii").splitlines()
           if line.strip() and not line.lstrip().startswith("#")]
for name, mount in (("SYSTEM", "/system"), ("PRODUCT", "/product"),
                    ("VENDOR", "/vendor")):
    selected = [e for e in entries if e[0].endswith("/" + name)]
    assert len(selected) == 1, (name, selected)
    assert selected[0][1:4] == [mount, "erofs", "ro"]
    assert "first_stage_mount" in selected[0][4]
swap = [e for e in entries if e[0] == "/dev/block/zram0"]
assert len(swap) == 1
assert "zramsize=2684354560,max_comp_streams=8" in swap[0][4]

board = (ROOT / "arch/arm64/boot/dts/exynos/exynos8895-dream2lte_common.dtsi").read_text()
assert "max-freq = <2002000>;" in board
assert "max-freq = <2704000>;" in board
print("PASS: donor fstab byte-identical; EROFS-only profile kept optional; ALice OC limits preserved")
