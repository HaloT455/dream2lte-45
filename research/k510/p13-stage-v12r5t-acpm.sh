#!/usr/bin/env bash
# P13: source-exact donor ACPM/S2MPS17 compile-compatibility lab.
# NO hardware enabling, NO new DT supply/regulator writes, NO boot.img.
set -euo pipefail
DONOR="$1"
TREE="$2"
PIN=3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3
git -C "$DONOR" cat-file -e "$PIN^{commit}" || {
  echo "Missing exact V12R5T donor commit $PIN" >&2
  exit 20
}
test -s "$TREE/Makefile"
copy_exact() {
  local p="$1"
  mkdir -p "$TREE/$(dirname "$p")"
  git -C "$DONOR" show "$PIN:$p" > "$TREE/$p"
  test -s "$TREE/$p"
  printf 'P13 donor import %-66s sha256=' "$p"
  sha256sum "$TREE/$p" | awk '{print $1}'
}
# Exact four-layer dependency chain. None is linked or enabled for runtime.
copy_exact include/soc/samsung/acpm_ipc_ctrl.h
copy_exact include/soc/samsung/acpm_mfd.h
copy_exact include/linux/mfd/samsung/s2mps17.h
copy_exact include/linux/mfd/samsung/s2mps17-private.h
copy_exact drivers/soc/samsung/acpm/acpm_mfd.c
copy_exact drivers/mfd/s2mps17_core.c
copy_exact drivers/mfd/s2mps17_irq.c
copy_exact drivers/regulator/s2mps17.c
# Scope limitation: this lab does NOT transfer ACPM IPC firmware, dynamic
# plugin loader, FW headers or CAL interface. Those must precede device probe.
test -s "$TREE/drivers/soc/samsung/acpm/acpm_mfd.c"
echo "P13 copied pinned V12R5T ACPM MFD + S2MPS17 files for 5.10 compile analysis."
echo "P13 ACPM firmware IPC/runtime NOT PORTED; PMIC DT probe stays disabled."
