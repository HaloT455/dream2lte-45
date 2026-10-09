#!/usr/bin/env bash
# Compile-only transplant of Linux 6.13's Exynos8895 *S8* DTS into Linux 5.10.262.
# This is NOT a driver port and NOT a G955F/dream2lte DTB. NEVER FLASH.
set -euo pipefail
WORKDIR="${K510_WORKDIR:-$HOME/alice-k510}"
SRC="$WORKDIR/linux-5.10.262"
OUT="$WORKDIR/out-generic-arm64"
UPSTREAM_REF="v6.13"
[[ -f "$SRC/Makefile" ]] || { echo 'Fetch 5.10 source first: bootstrap.sh --fetch' >&2; exit 2; }
[[ "$(make -s -C "$SRC" kernelversion)" == "5.10.262" ]] || {
 echo 'Expected genuine Linux v5.10.262 source' >&2; exit 3;
}
command -v curl >/dev/null || { echo 'Please install curl' >&2; exit 4; }
mkdir -p "$SRC/arch/arm64/boot/dts/exynos" "$SRC/arch/arm64/boot/dts/arm/samsung"
readonly files=(
 "arch/arm64/boot/dts/exynos/exynos8895.dtsi"
 "arch/arm64/boot/dts/exynos/exynos8895-pinctrl.dtsi"
 "arch/arm64/boot/dts/exynos/exynos8895-dreamlte.dts"
 "arch/arm64/boot/dts/exynos/exynos-pinctrl.h"
 "include/dt-bindings/clock/samsung,exynos8895.h"
)
for file in "${files[@]}"; do
 mkdir -p "$SRC/$(dirname "$file")"
 curl --fail --location --silent --show-error --retry 3 \
  "https://raw.githubusercontent.com/torvalds/linux/$UPSTREAM_REF/$file" -o "$SRC/$file"
 test -s "$SRC/$file"
done
# Linux 6.13 ARM64 DTS includes a shared ARM32 Samsung syscon-reset DTSI.
curl --fail --location --silent --show-error --retry 3 \
 "https://raw.githubusercontent.com/torvalds/linux/$UPSTREAM_REF/arch/arm/boot/dts/samsung/exynos-syscon-restart.dtsi" \
 -o "$SRC/arch/arm64/boot/dts/arm/samsung/exynos-syscon-restart.dtsi"
test -s "$SRC/arch/arm64/boot/dts/arm/samsung/exynos-syscon-restart.dtsi"

# Register the SM-G950F reference device tree ONLY. SM-G955F needs independent validation.
dts_makefile="$SRC/arch/arm64/boot/dts/exynos/Makefile"
if ! grep -q 'exynos8895-dreamlte.dtb' "$dts_makefile"; then
  printf '\n# Linux 6.13 Exynos8895 S8 donor DTS compilation ONLY. Not a device port.\ndtb-$(CONFIG_ARCH_EXYNOS) += exynos8895-dreamlte.dtb\n' >> "$dts_makefile"
fi
if [[ ! -f "$OUT/.config" ]]; then
 mkdir -p "$OUT"
 make -C "$SRC" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- defconfig
fi
grep -q '^CONFIG_ARCH_EXYNOS=y$' "$OUT/.config" || {
 echo "CONFIG_ARCH_EXYNOS must be set to build donor device-tree" >&2; exit 5;
}
make -C "$SRC" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
 -j"${K510_JOBS:-2}" dtbs
DTB="$OUT/arch/arm64/boot/dts/exynos/exynos8895-dreamlte.dtb"
test -s "$DTB"
if command -v fdtget >/dev/null; then
 model="$(fdtget -t s "$DTB" / model)"
 echo "Donor DTB model: $model"
 [[ "$model" == 'Samsung Galaxy S8 (SM-G950F)' ]] || {
  echo "Unexpected model; refusing artifact" >&2; exit 6;
 }
fi
mkdir -p "$WORKDIR/reference-dtb"
cp "$DTB" "$WORKDIR/reference-dtb/exynos8895-dreamlte-SM-G950F-DONOR-NOT-FOR-G955F.dtb"
cat > "$WORKDIR/reference-dtb/README-NOT-FLASHABLE.txt" <<'DOC'
Linux 5.10.262 dtc proof of Linux v6.13 donor Exynos8895 device-tree.
Board is dreamlte SM-G950F, NOT dream2lte SM-G955F.
No runtime kernel driver support or S8+ memory map was ported.
It is NOT a bootable or flashable Galaxy S8+ image.
Never flash this DTB.
DOC
sha256sum "$DTB" > "$WORKDIR/reference-dtb/dtb.sha256"
echo 'DTS DONOR COMPILED, not a dream2lte device port. NO FLASH.'
