#!/usr/bin/env bash
# Download *reference only* Exynos8895 support files from verified Linux v6.13.
# Linux 6.13 interfaces differ from Linux 5.10; DO NOT copy blindly or flash.
set -euo pipefail
REF=v6.13
WORKDIR="${K510_WORKDIR:-$HOME/alice-k510}"
DEST="$WORKDIR/reference-exynos8895-$REF"
command -v curl >/dev/null || { echo "Install curl first" >&2; exit 2; }
mkdir -p "$DEST"
files=(
  arch/arm64/boot/dts/exynos/exynos8895.dtsi
  arch/arm64/boot/dts/exynos/exynos8895-pinctrl.dtsi
  arch/arm64/boot/dts/exynos/exynos8895-dreamlte.dts
  include/dt-bindings/clock/samsung,exynos8895.h
  drivers/clk/samsung/clk-exynos8895.c
  drivers/clk/samsung/clk-exynos-arm64.c
  drivers/clk/samsung/clk-exynos-arm64.h
  drivers/pinctrl/samsung/pinctrl-exynos-arm64.c
)
for file in "${files[@]}"; do
  mkdir -p "$DEST/$(dirname "$file")"
  url="https://raw.githubusercontent.com/torvalds/linux/$REF/$file"
  echo "Reference: $file"
  curl --fail --location --silent --show-error "$url" -o "$DEST/$file"
done
(cd "$DEST" && sha256sum "${files[@]}") > "$DEST/SHA256SUMS"
cat > "$DEST/README-NOT-A-PORT.txt" <<'TXT'
Reference snapshot from Linux v6.13: Exynos8895 DTS, clocks and pinctrl.
SM-G950F dreamlte DTS is NOT SM-G955F dream2lte DTS.
These references are NOT a drop-in Linux 5.10 patch.
DO NOT flash; no compiled boot image exists here.
TXT
echo "References saved in $DEST"
echo 'Next: adapt DT and platform driver interfaces to Linux 5.10, compile with dtc, validate board model.'
