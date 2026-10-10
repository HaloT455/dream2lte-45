#!/usr/bin/env bash
# P14 test-harness repair: register copied donor files in Linux 5.10 Kbuild.
# This modifies ONLY the temporary downloaded CI source tree, not phone or firmware.
set -euo pipefail
SRC="$1"
OUT="$2"

test -s "$OUT/.config"
test -s "$SRC/drivers/soc/samsung/Makefile"
test -s "$SRC/drivers/mfd/Makefile"
test -s "$SRC/drivers/regulator/Makefile"

register_rule() {
  local file="$1" rule="$2"
  if ! grep -qxF "$rule" "$file"; then
    printf '\n%s\n' "$rule" >> "$file"
  fi
}

for source in \
  drivers/soc/samsung/acpm/acpm_mfd.c \
  drivers/mfd/s2mps17_core.c \
  drivers/mfd/s2mps17_irq.c \
  drivers/regulator/s2mps17.c; do
  test -s "$SRC/$source" || { echo "P14 missing donor source: $source" >&2; exit 30; }
done

mkdir -p "$SRC/drivers/soc/samsung/acpm"
touch "$SRC/drivers/soc/samsung/acpm/Makefile"
register_rule "$SRC/drivers/soc/samsung/Makefile" 'obj-y += acpm/'
register_rule "$SRC/drivers/soc/samsung/acpm/Makefile" 'obj-y += acpm_mfd.o'
register_rule "$SRC/drivers/mfd/Makefile" 'obj-y += s2mps17_core.o'
register_rule "$SRC/drivers/mfd/Makefile" 'obj-y += s2mps17_irq.o'
register_rule "$SRC/drivers/regulator/Makefile" 'obj-y += s2mps17.o'
echo 'P14 registered four donor translation units in temporary Kbuild (compile lab only).'
echo 'P14 does NOT link Image, activate DT, write regulator values, or package BOOT.'
