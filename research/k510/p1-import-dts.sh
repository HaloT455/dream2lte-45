#!/usr/bin/env bash
# Stage P1A: bring Exynos8895 SoC DTS from Linux v6.13 into genuine Linux v5.10.
# Not a bootable board port: board memory/reserved-memory/storage/boot shim unverified.
set -euo pipefail
TREE="${1:?Usage: $0 /path/to/linux-5.10.262}"
[[ -f "$TREE/Makefile" ]] || { echo "No kernel source" >&2; exit 2; }
[[ "$(make -s -C "$TREE" kernelversion)" == 5.10.* ]] || { echo "Must use genuine Linux 5.10" >&2; exit 3; }
BASE=https://raw.githubusercontent.com/torvalds/linux/v6.13
DTS="$TREE/arch/arm64/boot/dts/exynos"
mkdir -p "$DTS" "$TREE/include/dt-bindings/clock"
fetch() {
  local path="$1" dest="$2"
  echo "Fetching donor v6.13: $path"
  curl -fL --retry 3 --silent --show-error "$BASE/$path" -o "$dest"
  test -s "$dest"
}
fetch arch/arm64/boot/dts/exynos/exynos8895.dtsi "$DTS/exynos8895.dtsi"
fetch arch/arm64/boot/dts/exynos/exynos8895-pinctrl.dtsi "$DTS/exynos8895-pinctrl.dtsi"
fetch arch/arm64/boot/dts/exynos/exynos-pinctrl.h "$DTS/exynos-pinctrl.h"
fetch include/dt-bindings/clock/samsung,exynos8895.h "$TREE/include/dt-bindings/clock/samsung,exynos8895.h"

# Linux v6.13 has a cross-architecture DTS include unavailable in Linux 5.10;
# inline the exact common syscon reboot definition (no functional rewrite).
fetch arch/arm/boot/dts/samsung/exynos-syscon-restart.dtsi "$DTS/exynos8895-syscon-restart.dtsi"
python3 - "$DTS/exynos8895.dtsi" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
a='#include "arm/samsung/exynos-syscon-restart.dtsi"'
assert s.count(a)==1, "donor include unexpectedly changed"
p.write_text(s.replace(a, '#include "exynos8895-syscon-restart.dtsi"'))
PY

# Intentionally minimal, board-specific compatible. Do not invent memory layout.
cat > "$DTS/exynos8895-dream2lte.dts" <<'DTS'
/dts-v1/;
// SPDX-License-Identifier: GPL-2.0 OR BSD-3-Clause
/*
 * Alice K510 P1A -- Samsung Galaxy S8+ / SM-G955F
 * DT compilation skeleton ONLY. NOT A BOOTABLE DEVICE TREE.
 * Board RAM map, reserved memory, bootloader handoff and vendor drivers
 * must be ported and verified before a boot image can be attempted.
 */
#include "exynos8895.dtsi"

/ {
	model = "Samsung Galaxy S8+ (SM-G955F) - P1 nonbootable skeleton";
	compatible = "samsung,dream2lte", "samsung,exynos8895";
};
DTS

python3 - "$DTS/Makefile" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
entry='\n# Alice K510 P1A: compile-only S8+ DTS (not boot-ready)\ndtb-$(CONFIG_ARCH_EXYNOS) += exynos8895-dream2lte.dtb\n'
if 'exynos8895-dream2lte.dtb' not in s:
    p.write_text(s.rstrip()+'\n'+entry)
PY
echo "P1A: Exynos8895 DTS sources present, dream2lte DTB build target registered."
echo "P1A NOT BOOTABLE: missing verified board RAM map, storage, display and boot shim."
