#!/usr/bin/env bash
# P21 exact 8895 calibration executor: TEMP Linux 5.10 C/link only.
set -euo pipefail
WORKSPACE="${1:?workspace}"
TREE="${2:?linux510_tree}"
test -s "$WORKSPACE/research/k510/p21-ufs8895-engine.c"
test -s "$WORKSPACE/research/k510/p21-ufs8895-engine.h"
test -s "$TREE/drivers/scsi/ufs/alice-ufs8895-calibration.h"
test -s "$TREE/drivers/scsi/ufs/alice-ufs8895-calibration.c"
test ! -e "$TREE/drivers/scsi/ufs/alice-ufs8895-engine.c"
test ! -e "$TREE/drivers/scsi/ufs/alice-ufs8895-engine.h"
cp "$WORKSPACE/research/k510/p21-ufs8895-engine.c" "$TREE/drivers/scsi/ufs/alice-ufs8895-engine.c"
cp "$WORKSPACE/research/k510/p21-ufs8895-engine.h" "$TREE/drivers/scsi/ufs/alice-ufs8895-engine.h"
test "$(grep -c 'obj-y += alice-ufs8895-calibration.o' "$TREE/drivers/scsi/ufs/Makefile")" = 1
printf '\n# P21 research-only, intentionally no platform UFS probe\nobj-y += alice-ufs8895-engine.o\n' >> "$TREE/drivers/scsi/ufs/Makefile"
sha256sum "$TREE/drivers/scsi/ufs/alice-ufs8895-engine."{c,h}
echo 'P21 hardware access is explicitly gated and not registered; UFS DT stays disabled.'
