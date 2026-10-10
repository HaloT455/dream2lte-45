#!/usr/bin/env bash
# P18 stage 2: EXACT V12R5T dependency headers for vendor UFS C-API
# compile analysis. Disposable Linux 5.10 tree ONLY. No runtime/flash.
set -euo pipefail
DONOR="$1"
TREE="$2"
PIN=3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3
git -C "$DONOR" cat-file -e "$PIN^{commit}"
for header in \
  include/soc/samsung/exynos-pm.h \
  include/soc/samsung/exynos-powermode.h \
  include/soc/samsung/cal-if.h \
  include/linux/soc/samsung/exynos-soc.h \
  include/linux/exynos-ss.h \
  drivers/soc/samsung/cal-if/pmucal_system.h \
  drivers/soc/samsung/cal-if/pmucal_common.h \
  drivers/soc/samsung/cal-if/pwrcal-env.h; do
  test -f "$TREE/$header" && {
    echo "P18 dependency already exists: $header (will replace ONLY in disposable CI tree)"
  }
  mkdir -p "$TREE/$(dirname "$header")"
  git -C "$DONOR" show "$PIN:$header" > "$TREE/$header"
  test -s "$TREE/$header"
  sha256sum "$TREE/$header"
done
echo 'P18 dependency headers staged from EXACT V12R5T, without runtime CAL, PMIC or Speedy drivers.'
echo 'The CONFIG_CAL_IF flag may be defined ONLY during one vendor C compilation test.'
