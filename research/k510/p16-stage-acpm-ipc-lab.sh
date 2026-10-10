#!/usr/bin/env bash
# P16 lab ONLY: stage exact Samsung 4.4 ACPM firmware control + IPC sources
# into a disposable Linux 5.10 build tree; never probe hardware or make BOOT.
set -euo pipefail
DONOR="$1"
TREE="$2"
PIN=3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3
git -C "$DONOR" cat-file -e "$PIN^{commit}"
copy_pinned() {
  local p="$1"
  mkdir -p "$TREE/$(dirname "$p")"
  git -C "$DONOR" show "$PIN:$p" > "$TREE/$p"
  test -s "$TREE/$p"
  printf 'P16 pinned donor %-72s ' "$p"
  sha256sum "$TREE/$p"
}
for path in \
  drivers/soc/samsung/acpm/acpm.c \
  drivers/soc/samsung/acpm/acpm.h \
  drivers/soc/samsung/acpm/acpm_ipc.c \
  drivers/soc/samsung/acpm/acpm_ipc.h \
  drivers/soc/samsung/acpm/fw_header/common.h \
  drivers/soc/samsung/acpm/fw_header/framework.h \
  drivers/soc/samsung/cal-if/fvmap.h; do
  copy_pinned "$path"
done

# P14 already registers acpm_mfd.o in disposable Kbuild.
FILE="$TREE/drivers/soc/samsung/acpm/Makefile"
test -f "$FILE"
for item in 'obj-y += acpm.o' 'obj-y += acpm_ipc.o'; do
  grep -qxF "$item" "$FILE" || printf '%s\n' "$item" >> "$FILE"
done

echo 'P16 ACPM control/IPCs + firmware-layout *headers* staged for C/link audit.'
echo 'The real firmware binaries, mailbox hardware, PMIC and UFS runtime remain DISABLED.'
