#!/usr/bin/env python3
"""P24 research-only Exynos8895 UFS platform binding into disposable 5.10.

Pin known physical MMIO addresses from Samsung 4.4. The full binding remains
completely disabled, requires independent review of clock/regulator/ACPM and
secure firmware, and cannot run during P24 CI or a booted default DTS.
"""
from pathlib import Path
import re, sys

def stop(s):
    raise SystemExit("P24 REFUSED: " + s)

if len(sys.argv) != 3:
    stop("usage: python3 p24-stage-ufs8895-bind.py WORKSPACE LINUX510")
root, tree = (Path(x) for x in sys.argv[1:])
ufs = tree / "drivers/scsi/ufs"
dts = tree / "arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
cpath = ufs / "alice-ufs8895-host.c"
hpath = ufs / "alice-ufs8895-host.h"
for p in [cpath, hpath, ufs/"alice-ufs8895-smc.c",
          ufs/"alice-ufs8895-engine.c", dts]:
    if not p.exists():
        stop("missing previous stage: " + str(p))
for ext in ("c", "h"):
    dst=ufs/("alice-ufs8895-bind."+ext)
    if dst.exists(): stop("P24 binder already installed")
    dst.write_text((root/"research/k510"/("p24-ufs8895-bind."+ext)).read_text())

# The only missing runtime connection in P23 is hba->priv allocation.
# Bind resource handles without claiming runtime-ready firmware/power.
code=cpath.read_text()
needle='#include "alice-ufs8895-host.h"'
if code.count(needle)!=1: stop("host include anchor changed")
code=code.replace(needle,needle+'\n#include "alice-ufs8895-bind.h"',1)
original='''static int alice_8895_variant_init(struct ufs_hba *hba)
{
\tstruct alice_8895_host *ctx = alice_8895_ctx(hba);

\t/* No P23 platform probe ever populates hba->priv. */
\tif (!ctx)
\t\treturn -EPERM;
\treturn alice_8895_prepare_power(ctx);
}'''
patched='''static int alice_8895_variant_init(struct ufs_hba *hba)
{
\tstruct alice_8895_host *ctx = alice_8895_ctx(hba);
\tint ret;

\tif (!ctx) {
\t\tret = alice_8895_ufs_bind_host(hba);
\t\tif (ret)
\t\t\treturn ret;
\t\tctx = alice_8895_ctx(hba);
\t}
\tif (!ctx)
\t\treturn -EPERM;
\t/* The P24 bind step never marks hardware/firmware reviewed:
\t * alice_8895_prepare_power() is fail-closed until independent audit.
\t */
\treturn alice_8895_prepare_power(ctx);
}'''
if code.count(original)!=1: stop("P23 native variant init signature/contract changed")
code=code.replace(original,patched,1)
cpath.write_text(code)

mk=ufs/"Makefile"
body=mk.read_text()
if body.count("obj-y += alice-ufs8895-host.o")!=1: stop("P23 Kbuild not unique")
if "alice-ufs8895-bind.o" in body: stop("duplicate P24 bind object")
mk.write_text(body+"\n# P24 NO-FLASH native research-only platform binding\nobj-y += alice-ufs8895-bind.o\n")

body=dts.read_text()
anchor='''    alice_ufs_embd: ufs@11120000 {
        compatible = "samsung,exynos7-ufs";
        reg = <0x11120000 0x200>,
              <0x11121100 0x200>,
              <0x11110000 0x8000>,
              <0x11130000 0x100>;
        reg-names = "hci", "vs_hci", "unipro", "protector";'''
staged='''    alice_ufs_embd: ufs@11120000 {
        /* P24 matches only this RESEARCH driver, never Linux Exynos7. */
        compatible = "alice,exynos8895-ufs-research";
        /* The last four registers verified in V12R5T /ufs@0x11120000.
         * PMU/sysreg overlaps require independent Linux ownership audit. */
        reg = <0x11120000 0x200>,
              <0x11121100 0x200>,
              <0x11110000 0x8000>,
              <0x11130000 0x100>,
              <0x11124000 0x800>,
              <0x16480724 0x4>,
              <0x11020700 0x4>,
              <0x11021150 0x4>;
        reg-names = "hci", "vs_hci", "unipro", "protector",
                    "phy_pma", "phy_isolation", "io_coherency",
                    "tcxo_select";'''
if body.count(anchor)!=1: stop("expected original disabled UFS DT P4 anchor missing")
body=body.replace(anchor,staged,1)
node = re.search(r'alice_ufs_embd:\s*ufs@11120000\s*\{(.*?)\n\s*\};',body,re.S)
if not node: stop("p24 DTS malformed")
n=node.group(1)
if 'status = "disabled";' not in n: stop("UFS status enabled!")
if 'alice,hardware-audit-passed' in n: stop("unreviewed firmware audit property inserted!")
if 'samsung,exynos7-ufs' in n: stop("generic Exynos7 compatible still present")
dts.write_text(body)
print("P24: actual 5.10 host binding + P23 context glue compiled; DT=disabled, protected probe")
print("P24: verified 8 original controller/PMA/sysreg resource ranges; NEVER FLASH")
