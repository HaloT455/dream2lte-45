#!/usr/bin/env bash
# P2B: create a distinct dream2lte uniLoader board profile from S8 donor.
# Crucially, disable all unverified PMIC and DECON MMIO writes.
# This produces only code for compile-time study; hardware handoff unproven.
set -euo pipefail
SRC="$1"
test -s "$SRC/configs/dreamlte_defconfig"
python3 - "$SRC" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
old_config=(root/"configs/dreamlte_defconfig").read_text()
assert old_config.count("CONFIG_SAMSUNG_DREAMLTE=y")==1
new_config=old_config.replace("CONFIG_SAMSUNG_DREAMLTE=y",
                              "CONFIG_SAMSUNG_DREAM2LTE=y")
(root/"configs/dream2lte_defconfig").write_text(new_config)

kconfig=root/"board/Kconfig"
t=kconfig.read_text()
anchor="\tconfig SAMSUNG_DREAMLTE\n"
assert t.count(anchor)==1
if "config SAMSUNG_DREAM2LTE" not in t:
    new='\tconfig SAMSUNG_DREAM2LTE\n\t\tbool "Research Samsung Galaxy S8+ (SM-G955F)"\n\t\tdefault n\n\t\tdepends on EXYNOS_8895\n\t\thelp\n\t\t  P2 compiler research only; power and boot are NOT validated.\n\n'
    kconfig.write_text(t.replace(anchor,new+anchor))

mk=root/"board/Makefile"
t=mk.read_text()
anchor="lib-$(CONFIG_SAMSUNG_DREAMLTE) += samsung/board-dreamlte.o\n"
assert t.count(anchor)==1
if "CONFIG_SAMSUNG_DREAM2LTE" not in t:
    mk.write_text(t.replace(anchor,
                   "lib-$(CONFIG_SAMSUNG_DREAM2LTE) += samsung/board-dream2lte.o\n"+anchor))

c=root/"board/samsung/board-dream2lte.c"
if c.exists():
    raise SystemExit("dream2lte board already exists; stop to avoid overwrite")
t=(root/"board/samsung/board-dreamlte.c").read_text()
assert t.count("s2mps17_setup();")==1
assert t.count("*(int*) (DECON_F_BASE + HW_SW_TRIG_CONTROL) = 0x1281;")==1
t=t.replace("dreamlte","dream2lte")
t=t.replace("s2mps17_setup();",
            "/* S8+ PMIC LDO register sequence UNVERIFIED: intentionally disabled. */\n"
            "\t(void)s2mps17_setup;")
t=t.replace("*(int*) (DECON_F_BASE + HW_SW_TRIG_CONTROL) = 0x1281;",
            "/* S8+ DECON MMIO write UNVERIFIED: intentionally disabled. */")
# Donor simplefb at 0xCC000000 is WITHIN live camera reserved memory
# (0xC0400000..0xCE800000). Block all framebuffer registration.
assert t.count(".devices = dream2lte_devices,")==1
assert t.count(".num_devices = ARRAY_SIZE(dream2lte_devices),")==1
t=t.replace(".devices = dream2lte_devices,",
            "/* S8+ simplefb 0xCC000000 overlaps camera carveout; disabled. */\n"
            "    .devices = dream2lte_devices,")
t=t.replace(".num_devices = ARRAY_SIZE(dream2lte_devices),",
            "    .num_devices = 0,")
t=t.replace("/* SPDX-License-Identifier: GPL-2.0 */",
            "/* SPDX-License-Identifier: GPL-2.0 */\n"
            "/* K510 P2B: experimental SM-G955F profile derived from donor SM-G950F. */\n"
            "/* NOT FLASHABLE. Hardware clocks/regulators/display unverified. */",1)
c.write_text(t)
print("P2B dream2lte uniLoader target configured with MMIO/PMIC writes disabled")
PY
