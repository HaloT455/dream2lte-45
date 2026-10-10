#!/usr/bin/env bash
# Stage audited Samsung Exynos8895 ARM64 SMC/FMP ABI bridge into disposable Linux 5.10.262.
set -euo pipefail
WS="${1:?workspace}"
SRC="${2:?linux510_tree}"
D="$SRC/drivers/scsi/ufs"
test -s "$SRC/include/linux/arm-smccc.h"
test -s "$D/alice-ufs8895-engine.c"
test -s "$D/alice-ufs8895-calibration.c"
test ! -e "$D/alice-ufs8895-secure.c"
test ! -e "$D/alice-ufs8895-secure.h"
cp "$WS/research/k510/p22-ufs8895-secure.c" "$D/alice-ufs8895-secure.c"
cp "$WS/research/k510/p22-ufs8895-secure.h" "$D/alice-ufs8895-secure.h"
test -s "$D/alice-ufs8895-secure.c"
test -s "$D/alice-ufs8895-secure.h"
grep -q 'obj-y += alice-ufs8895-engine.o' "$D/Makefile"
printf '\n# P22 original Samsung SMCCC/FMP bridge, NO RUNTIME CALLER\nobj-y += alice-ufs8895-secure.o\n' >> "$D/Makefile"
sha256sum "$D/alice-ufs8895-secure."{c,h}
echo 'P22 UFS secure bridge compiled only; no registered UFS driver, no real SMC execution.'
