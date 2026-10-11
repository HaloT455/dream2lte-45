#!/usr/bin/env bash
# P23 unregistered host variant: disposable Linux 5.10.262 ONLY.
set -euo pipefail
ROOT="${1:?repo}"
TREE="${2:?linux510tree}"
UFS="$TREE/drivers/scsi/ufs"
test -s "$UFS/alice-ufs8895-calibration.c"
test -s "$UFS/alice-ufs8895-engine.c"
test -s "$UFS/alice-ufs8895-smc.c"
test -s "$TREE/include/linux/regulator/consumer.h"
test -s "$TREE/include/linux/clk.h"
test ! -e "$UFS/alice-ufs8895-host.c"
test ! -e "$UFS/alice-ufs8895-host.h"
cp "$ROOT/research/k510/p23-ufs8895-host.c" "$UFS/alice-ufs8895-host.c"
cp "$ROOT/research/k510/p23-ufs8895-host.h" "$UFS/alice-ufs8895-host.h"
printf '\n# P23 unregistered 8895 host variant, no platform device, NO-FLASH\nobj-y += alice-ufs8895-host.o\n' >> "$UFS/Makefile"
test "$(grep -Fc 'obj-y += alice-ufs8895-host.o' "$UFS/Makefile")" = 1
if grep -En '(^|\\W)(module_platform_driver|builtin_platform_driver|platform_driver_register|ufshcd_pltfrm_init|of_match_table|of_device_id)' "$UFS/alice-ufs8895-host.c"; then
  echo 'P23 REFUSED: hardware probe/driver registration forbidden' >&2
  exit 70
fi
echo 'P23: native Linux 5.10 typed UFS host callbacks staged; zero registered clients'
