#!/usr/bin/env bash
# P17 strict source-exact S2MPS17 ADC/powermeter dependency import.
# Only modifies disposable CI Linux 5.10.262 tree. No PMIC enable/boot output.
set -euo pipefail
DONOR="$1"; TREE="$2"
PIN=3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3
SRC=drivers/regulator/s2mps17_powermeter.c
DST="$TREE/$SRC"
test -s "$TREE/drivers/regulator/s2mps17.c"
git -C "$DONOR" cat-file -e "$PIN^{commit}"
test ! -e "$DST" || { echo "P17 refused duplicate powermeter source" >&2; exit 29; }
mkdir -p "$(dirname "$DST")"
git -C "$DONOR" show "$PIN:$SRC" > "$DST"
test -s "$DST"
grep -q 'void s2mps17_powermeter_init(' "$DST"
grep -q 'void s2mps17_powermeter_deinit(' "$DST"
MAKEFILE="$TREE/drivers/regulator/Makefile"
if grep -q 's2mps17_powermeter\.o' "$MAKEFILE"; then
  echo "P17 refused preexisting powermeter Kbuild rule" >&2
  exit 30
fi
printf '\nobj-y += s2mps17_powermeter.o\n' >> "$MAKEFILE"
sha256sum "$DST"
echo "P17 exact donor powermeter added to temporary Linux 5.10 kernel Kbuild. NEVER FLASH."
