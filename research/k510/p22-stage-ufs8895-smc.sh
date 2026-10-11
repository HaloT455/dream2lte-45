#!/usr/bin/env bash
set -euo pipefail
WORKSPACE="${1:?workspace}"
TREE="${2:?linux510tree}"
DST="$TREE/drivers/scsi/ufs"
test -s "$DST/alice-ufs8895-engine.c"
test -s "$DST/alice-ufs8895-calibration.c"
test -s "$TREE/include/linux/arm-smccc.h"
test ! -e "$DST/alice-ufs8895-smc.c"
test ! -e "$DST/alice-ufs8895-smc.h"
cp "$WORKSPACE/research/k510/p22-ufs8895-smc.c" "$DST/alice-ufs8895-smc.c"
cp "$WORKSPACE/research/k510/p22-ufs8895-smc.h" "$DST/alice-ufs8895-smc.h"
printf '\n# P22 secure monitor bridge research, NO hardware clients\nobj-y += alice-ufs8895-smc.o\n' >> "$DST/Makefile"
grep -qx 'obj-y += alice-ufs8895-smc.o' <(tail -n1 "$DST/Makefile")
echo 'P22 native SMCCC bridge staged with firmware access disabled by default'
