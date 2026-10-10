#!/usr/bin/env python3
"""P19 narrow, real Linux-5.10 UFS ABI migration (no stubs, no boot code).

Apply only verified one-to-one UniPro L2 attribute macro renames to
EXACT original Samsung 4.4 UFS C source, in quarantined CI test directory.
All changed names must exist in genuine Linux 5.10 unipro.h.
Other semantic API mismatches (SMC, variant_ops, QoS, quirks) are deliberately
left as compile-time errors until implemented and reviewed.
"""
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    sys.exit("Usage: p19-port-ufs-abi.py LINUX_5_10_KERNEL_TREE")
tree = Path(sys.argv[1])
path = tree / "drivers/scsi/ufs/alice-p18-vendor/ufs-exynos-vendor.c"
native = tree / "drivers/scsi/ufs/unipro.h"
if not path.is_file() or not native.is_file():
    sys.exit("P19 refused missing staged original UFS or native UniPro header")
source = path.read_text()
modern = native.read_text()
aliases = {
    "FC0PROTTIMEOUTVAL": "DL_FC0PROTTIMEOUTVAL",
    "TC0REPLAYTIMEOUTVAL": "DL_TC0REPLAYTIMEOUTVAL",
    "AFC0REQTIMEOUTVAL": "DL_AFC0REQTIMEOUTVAL",
}
for old, new in aliases.items():
    rx = r"\b" + old + r"\b"
    if not re.search(rx, source):
        raise SystemExit("P19 donor ABI changed, missing token " + old)
    if not re.search(r"^\s*#define\s+" + new + r"\b", modern, re.M):
        raise SystemExit("P19 Linux 5.10 lacks expected UniPro attribute " + new)
    source, number = re.subn(rx, new, source)
    print(f"P19 verified UniPro L2 macro {old} -> {new} ({number} references)")
path.write_text(source)
print("P19 one-to-one UniPro symbolic ABI mapping only. SMC, secure storage, variant callbacks and power rail handling intentionally not bypassed.")
