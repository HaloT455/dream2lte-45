#!/usr/bin/env python3
"""P27 Linux 5.10 Exynos8895 UFS clock + PMU resource link (NO FLASH).

Native clock IDs are pinned to upstream Linux v6.13 Exynos8895 clock driver.
Do NOT add GPIO fixed regulator node: that regulator might autonomously probe
and switch UFS VCC despite UFS status="disabled". This is blocked pending
verified baseline UFS fixed-regulator GPIO and rail ownership.
"""
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: python3 p27-fix-ufs-clock-pmu.py /linux510")
tree = Path(sys.argv[1])
dt = tree/"arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
bind = tree/"drivers/scsi/ufs/alice-ufs8895-bind.c"
clock_h = tree/"include/dt-bindings/clock/samsung,exynos8895.h"
dtsi = tree/"arch/arm64/boot/dts/exynos/exynos8895.dtsi"
for p in (dt,bind,clock_h,dtsi):
    if not p.is_file(): raise SystemExit("P27 missing source "+str(p))
keys = ["CLK_GOUT_FSYS0_UFS_EMBD_I_ACLK",
        "CLK_GOUT_FSYS0_UFS_EMBD_I_CLK_UNIPRO"]
src_h = clock_h.read_text()
for key in keys:
    if not re.search(r"(?m)^#define\s+"+key+r"\s+\d+\s*$", src_h):
        raise SystemExit("P27 native clock ID missing "+key)
src_dtsi=dtsi.read_text()
if 'cmu_fsys0: clock-controller@11000000' not in src_dtsi:
    raise SystemExit("P27 Exynos8895 FSYS0 controller missing")
if 'pmu_system_controller: system-controller@16480000' not in src_dtsi:
    raise SystemExit("P27 PMU syscon controller missing")

s=dt.read_text()
m=re.search(r'alice_ufs_embd:\s*ufs@11120000\s*\{(.*?)\n\s*\};',s,re.S)
if not m: raise SystemExit("P27 staged P24 UFS DT missing")
node=m.group(1)
if 'status = "disabled";' not in node:
    raise SystemExit("P27 UFS MUST remain disabled")
if 'alice,hardware-audit-passed' in node:
    raise SystemExit("P27 refused unauthorized runtime probe flag")
if 'clock-names' in node or 'samsung,pmu-phandle' in node:
    raise SystemExit("P27 duplicate or foreign clock/PMU properties")
if "vcc-supply" in node:
    raise SystemExit("P27 VCC fixed-regulator gpio has not been runtime verified")
anchor='''        reg-names = "hci", "vs_hci", "unipro", "protector",
                    "phy_pma", "phy_isolation", "io_coherency",
                    "tcxo_select";'''
if node.count(anchor)!=1: raise SystemExit("P27 original reg-names anchor changed")
n=node.replace(anchor,anchor+'''
        /* Exact Exynos8895 FSYS0 gate and UniPro IDs from v6.13.
         * Hardware gate stays closed and UFS node stays disabled. */
        clocks = <&cmu_fsys0 CLK_GOUT_FSYS0_UFS_EMBD_I_ACLK>,
                 <&cmu_fsys0 CLK_GOUT_FSYS0_UFS_EMBD_I_CLK_UNIPRO>;
        clock-names = "GATE_UFS_EMBD", "UFS_EMBD";
        samsung,pmu-phandle = <&pmu_system_controller>;
        /* vcc-supply intentionally UNBOUND: gpg0-0 fixed regulator must
         * be audited to avoid GPIO toggling from an unrelated probe. */''',1)
s=s[:m.start(1)]+n+s[m.end(1):]
if s.count('status = "disabled";')<1: raise SystemExit("P27 lost disabled guard")
dt.write_text(s)

source=bind.read_text()
a='#include <linux/platform_device.h>'
if source.count(a)!=1: raise SystemExit("P27 expected binder include not found")
source=source.replace(a,a+'\n#include <linux/mfd/syscon.h>',1)
a='''\tctx->vcc = devm_regulator_get(dev, "vcc");'''
if source.count(a)!=1: raise SystemExit("P27 expected binder VCC anchor missing")
source=source.replace(a,'''\
\t/* Syscon identity is a separate prerequisite to P23 power readiness.
\t * Never derive PMU/S2MPS17 readiness from a successful lookup.
\t */
\tctx->pmu = syscon_regmap_lookup_by_phandle(dev->of_node,
\t\t\t\t\t\t"samsung,pmu-phandle");
\tif (IS_ERR(ctx->pmu))
\t\treturn PTR_ERR(ctx->pmu);
\tctx->vcc = devm_regulator_get(dev, "vcc");''',1)
bind.write_text(source)
print("P27 CLOCK DT: FSYS0 gated HCI + UniPro phandles linked")
print("P27 PMU SYSCON: Exynos8895 registered syscon phandle linked")
print("P27 FIXED UFS VCC: NO property added; missing supplier remains hard-blocker")
print("P27 UFS disabled and no audit flag; no regulator or MMIO device activity")
