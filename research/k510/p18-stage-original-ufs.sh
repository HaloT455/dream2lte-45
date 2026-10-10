#!/usr/bin/env bash
# P18 non-flashable audit: stage ORIGINAL Exynos8895 Samsung 4.4 vendor UFS
# in an isolated subdirectory of disposable Linux 5.10.262.
set -euo pipefail
DONOR="$1"
TREE="$2"
PIN=3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3
git -C "$DONOR" cat-file -e "$PIN^{commit}"
test -s "$TREE/drivers/scsi/ufs/ufs-exynos.c"
test -s "$TREE/drivers/scsi/ufs/ufs-exynos.h"
LAB="$TREE/drivers/scsi/ufs/alice-p18-vendor"
mkdir -p "$LAB"
test ! -e "$LAB/ufs-exynos-vendor.c" || {
  echo 'P18 refused: vendor staging already exists' >&2; exit 21;
}
git -C "$DONOR" show "$PIN:drivers/scsi/ufs/ufs-exynos.c" > "$LAB/ufs-exynos-vendor.c"
git -C "$DONOR" show "$PIN:drivers/scsi/ufs/ufs-exynos.h" > "$LAB/ufs-exynos.h"
test -s "$LAB/ufs-exynos-vendor.c"
test -s "$LAB/ufs-exynos.h"
# Keep the original relative UFS header includes pointing to the 5.10 UFS
# host interfaces. This deliberately exposes real incompatible vendor APIs.
cat > "$LAB/Makefile" <<'EOF'
# P18 isolated SOURCE-COMPAT test only; not connected to the main kernel Makefile.
ccflags-y += -I$(srctree)/drivers/scsi/ufs
obj-y += ufs-exynos-vendor.o
EOF
echo 'P18: ORIGINAL Exynos8895 UFS driver + header in isolated compilation test.'
sha256sum "$LAB/ufs-exynos-vendor.c" "$LAB/ufs-exynos.h"
echo 'Never register in production Kbuild; native UFS remains separate and disabled in DT.'
