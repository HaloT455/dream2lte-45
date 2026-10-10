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


# Linux 5.10 moved sched_clock declaration to this public header; the older
# Samsung 4.4 code relied on transitive inclusions. This is a declaration-only
# port, not a fake API or hardware access shim.
python3 - "$TREE" <<'PY'
from pathlib import Path
import sys
tree = Path(sys.argv[1])
for rel in (
    "drivers/soc/samsung/acpm/acpm.c",
    "drivers/soc/samsung/acpm/acpm_ipc.c",
):
    path = tree / rel
    source = path.read_text()
    anchor = "#include <linux/kernel.h>\n"
    if source.count(anchor) != 1:
        raise SystemExit(f"P16 refused: unexpected source includes in {rel}")
    source = source.replace(anchor, anchor + "#include <linux/sched/clock.h>\n", 1)
    if rel.endswith("acpm_ipc.c"):
        # The pinned donor header already has #if CONFIG_EXYNOS_SNAPSHOT_ACPM
        # and a legitimate no-op trace macro for builds without snapshot.
        source = source.replace(
            "#include <linux/sched/clock.h>\n",
            "#include <linux/sched/clock.h>\n#include <linux/exynos-ss.h>\n",
            1,
        )
    path.write_text(source)
print("P16: declared sched_clock and existing snapshot instrumentation API.")
PY

# P14 already registers acpm_mfd.o in disposable Kbuild.
FILE="$TREE/drivers/soc/samsung/acpm/Makefile"
test -f "$FILE"
for item in 'obj-y += acpm.o' 'obj-y += acpm_ipc.o'; do
  grep -qxF "$item" "$FILE" || printf '%s\n' "$item" >> "$FILE"
done

echo 'P16 ACPM control/IPCs + firmware-layout *headers* staged for C/link audit.'
echo 'The real firmware binaries, mailbox hardware, PMIC and UFS runtime remain DISABLED.'
