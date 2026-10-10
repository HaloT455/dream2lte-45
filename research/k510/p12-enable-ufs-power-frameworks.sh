#!/usr/bin/env bash
# P12 compile-only native 5.10 UFS PHY, power/regulator, UFS host.
# S8+ specific UFS PHY / ACPM power is NOT enabled.
set -euo pipefail
TREE="$1"
OUT="$2"
test -s "$TREE/drivers/phy/samsung/phy-samsung-ufs.c"
test -s "$TREE/drivers/scsi/ufs/ufs-exynos.c"
test -s "$OUT/.config"
DTS="$TREE/arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
test -s "$DTS"
python3 - "$DTS" <<'PY'
from pathlib import Path
import sys,re
s=Path(sys.argv[1]).read_text()
node=re.search(r'alice_ufs_embd: ufs@11120000\s*\{(.*?)\n\s*\};',s,re.S)
if not node or not re.search(r'status\s*=\s*"disabled"\s*;',node.group(1)):
    raise SystemExit("P12 REFUSED: unvalidated UFS hardware must stay disabled")
print("P12: UFS DT remains status=disabled")
PY
cfg="$TREE/scripts/config"
test -f "$cfg"
"$cfg" --file "$OUT/.config" \
  --enable OF \
  --enable I2C \
  --enable REGULATOR \
  --enable REGMAP \
  --enable GENERIC_PHY \
  --enable MFD_SYSCON \
  --enable PHY_SAMSUNG_UFS \
  --enable SCSI \
  --enable SCSI_UFSHCD \
  --enable SCSI_UFSHCD_PLATFORM \
  --enable SCSI_UFS_EXYNOS
make -s -C "$TREE" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
for key in REGULATOR GENERIC_PHY PHY_SAMSUNG_UFS SCSI_UFSHCD SCSI_UFSHCD_PLATFORM SCSI_UFS_EXYNOS; do
  grep -qx "CONFIG_$key=y" "$OUT/.config" || {
    echo "P12 missing CONFIG_$key=y; stop" >&2
    exit 22
  }
done
echo "P12 native Linux 5.10 framework selection PASS"
echo "P12 does NOT include Exynos8895 PHY or ACPM/S2MPS17 implementations"
echo "P12 UFS remains disabled in DT and cannot boot Android as-is"
