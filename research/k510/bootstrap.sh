#!/usr/bin/env bash
# Download and smoke-build genuine Linux 5.10.262 separately from the 4.4 device kernel.
# Generic ARM64 Image is NEVER a flashable S8+ image.
set -euo pipefail

TAG=v5.10.262
EXPECTED=5.10.262
WORKDIR="${K510_WORKDIR:-$HOME/alice-k510}"
SRC="$WORKDIR/linux-$EXPECTED"
OUT="$WORKDIR/out-generic-arm64"
ACTION="${1:---fetch}"

case "$ACTION" in --fetch|--build) ;; *)
  echo "Usage: K510_WORKDIR=/path/on/large-disk bash $0 [--fetch|--build]" >&2
  exit 2 ;;
esac

mkdir -p "$WORKDIR"
if [[ ! -d "$SRC/.git" ]]; then
  if [[ -e "$SRC" ]]; then
    echo "ERROR: $SRC exists but is not a git checkout; refuse to replace it" >&2
    exit 3
  fi
  command -v git >/dev/null || { echo 'Install git first' >&2; exit 4; }
  echo "Fetching $TAG into $SRC..."
  git clone --depth 1 --single-branch --branch "$TAG" \
    https://github.com/gregkh/linux.git "$SRC"
fi

ORIGIN="$(git -C "$SRC" remote get-url origin)"
[[ "$ORIGIN" == 'https://github.com/gregkh/linux.git' ]] || {
  echo "ERROR: unexpected origin: $ORIGIN" >&2; exit 5;
}
VERSION="$(make -s -C "$SRC" kernelversion)"
[[ "$VERSION" == "$EXPECTED" ]] || {
  echo "ERROR: wrong kernel version: $VERSION" >&2; exit 6;
}
REF="$(git -C "$SRC" describe --tags --exact-match HEAD)"
[[ "$REF" == "$TAG" ]] || {
  echo "ERROR: source HEAD is not exactly $TAG: $REF" >&2; exit 7;
}
echo "Verified Linux $VERSION source @ $(git -C "$SRC" rev-parse --short HEAD)"
echo "Source: $SRC"

if [[ "$ACTION" == '--fetch' ]]; then
  echo "P0 fetch completed. No device kernel built; nothing flashable."
  exit 0
fi

command -v aarch64-linux-gnu-gcc >/dev/null || {
  echo 'ERROR: install gcc-aarch64-linux-gnu, binutils-aarch64-linux-gnu' >&2
  exit 8
}
mkdir -p "$OUT"
echo 'Compiling generic ARM64 defconfig smoke test (NOT dream2lte)...'
make -C "$SRC" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- defconfig
make -C "$SRC" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j"${K510_JOBS:-2}" Image

if [[ ! -s "$OUT/arch/arm64/boot/Image" ]]; then
  echo 'ERROR: no generic Image produced' >&2; exit 9
fi
sha256sum "$OUT/arch/arm64/boot/Image" | tee "$WORKDIR/generic-Image.sha256"
echo "COMPILATION SUCCESS: $OUT/arch/arm64/boot/Image"
echo 'NOT FLASHABLE: missing Exynos8895/dream2lte DT, early boot integration and vendor drivers.'
