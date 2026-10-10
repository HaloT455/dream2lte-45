#!/usr/bin/env python3
"""P15: CI-only Linux 5.10 compile bridge for pinned S2MPS17 donor.
NOT PRODUCTION CODE. No DT probe, no boot.img, Speedy adapter support NOT ported.
"""
from pathlib import Path
import subprocess
import sys

PIN = "3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3"
if len(sys.argv) != 3:
    raise SystemExit("Usage: p15-bridge-i2c.py DONOR_GIT_CHECKOUT LINUX510_TREE")
donor = Path(sys.argv[1])
tree = Path(sys.argv[2])
target = tree / "drivers/mfd/s2mps17_core.c"
if not target.is_file():
    raise SystemExit("P15 refused: missing exact staged S2MPS17 core source")
src = target.read_text()

original_start = "\ts2mps17->pmic = i2c_new_dummy("
original_end = "\n\ti2c_set_clientdata(s2mps17->pmic, s2mps17);"
if src.count(original_start) != 1 or src.count(original_end) != 1:
    raise SystemExit("P15 refused: original dummy-client block changed")
start = src.index(original_start)
end = src.index(original_end, start)

# Linux 5.10's replacement returns ERR_PTR, not NULL; unwind every created
# secondary client. Samsung Speedy is explicitly UNSUPPORTED; never silently
# redefine I2C_CLIENT_SPEEDY as zero or claim the PMIC path is functional.
replacement = """
\ts2mps17->pmic = i2c_new_dummy_device(i2c->adapter, I2C_ADDR_PMIC);
\tif (IS_ERR(s2mps17->pmic)) {
\t\tret = PTR_ERR(s2mps17->pmic);
\t\tgoto err_w_lock;
\t}
\ts2mps17->rtc = i2c_new_dummy_device(i2c->adapter, I2C_ADDR_RTC);
\tif (IS_ERR(s2mps17->rtc)) {
\t\tret = PTR_ERR(s2mps17->rtc);
\t\tgoto err_release_pmic;
\t}
\ts2mps17->debug_i2c = i2c_new_dummy_device(i2c->adapter, I2C_ADDR_DEBUG);
\tif (IS_ERR(s2mps17->debug_i2c)) {
\t\tret = PTR_ERR(s2mps17->debug_i2c);
\t\tgoto err_release_rtc;
\t}
\tif (pdata->use_i2c_speedy) {
#ifdef I2C_CLIENT_SPEEDY
\t\ts2mps17->pmic->flags |= I2C_CLIENT_SPEEDY;
\t\ts2mps17->rtc->flags |= I2C_CLIENT_SPEEDY;
\t\ts2mps17->debug_i2c->flags |= I2C_CLIENT_SPEEDY;
#else
\t\tdev_err(s2mps17->dev,
\t\t\t"Samsung I2C Speedy unavailable: fail closed (P15 test only)\\n");
\t\tret = -EOPNOTSUPP;
\t\tgoto err_release_debug;
#endif
\t}
"""
src = src[:start] + replacement.rstrip("\n") + src[end:]
old_unwind = """err_irq_init:
\ti2c_unregister_device(s2mps17->i2c);
err_w_lock:"""
new_unwind = """err_irq_init:
err_release_debug:
\ti2c_unregister_device(s2mps17->debug_i2c);
err_release_rtc:
\ti2c_unregister_device(s2mps17->rtc);
err_release_pmic:
\ti2c_unregister_device(s2mps17->pmic);
err_w_lock:"""
if src.count(old_unwind) != 1:
    raise SystemExit("P15 refused: original MFD error unwinding changed")
src = src.replace(old_unwind, new_unwind, 1)
if "#include <linux/err.h>" not in src:
    anchor = "#include <linux/slab.h>"
    if src.count(anchor) != 1:
        raise SystemExit("P15 refused: include anchor changed")
    src = src.replace(anchor, anchor + "\n#include <linux/err.h>", 1)
if "i2c_new_dummy(" in src:
    raise SystemExit("P15 refused: unconverted old API remains")

# Import original header; no false stub and no Exynos Snapshot runtime enablement.
head_path = "include/linux/exynos-ss.h"
blob = subprocess.check_output(
    ["git", "-C", str(donor), "show", f"{PIN}:{head_path}"]
)
if not blob.startswith(b"/*") or b"EXYNOS_SNAPSHOT_H" not in blob:
    raise SystemExit("P15 refused: unexpected donor snapshot header")
(tree / head_path).write_bytes(blob)
target.write_text(src)
print("P15 true Linux 5.10 dummy-client conversion and ERR_PTR cleanup staged.")
print("P15 original exynos-ss.h imported; no snapshot runtime implementation staged.")
print("P15 I2C Speedy branch returns -EOPNOTSUPP if unsupported. No hardware activation.")
