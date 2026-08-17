#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)

: "${ARCH:=arm64}"
: "${CROSS_COMPILE:=aarch64-none-linux-gnu-}"
: "${OUT:=$source_dir/out}"
: "${JOBS:=$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '1')}"
: "${KBUILD_BUILD_USER:=hlong}"
: "${KBUILD_BUILD_HOST:=aura}"
: "${KBUILD_BUILD_VERSION:=1}"
: "${KBUILD_BUILD_TIMESTAMP:=Tue Aug 4 16:42:47 +07 2026}"

export ARCH CROSS_COMPILE KBUILD_BUILD_USER KBUILD_BUILD_HOST
export KBUILD_BUILD_VERSION KBUILD_BUILD_TIMESTAMP

mkdir -p "$OUT"
make -C "$source_dir" O="$OUT" exynos8895-dream2lte_defconfig
make -C "$source_dir" -j"$JOBS" O="$OUT" Image dtb.img

printf 'Kernel: %s\n' "$OUT/arch/arm64/boot/Image"
printf 'DTB:    %s\n' "$OUT/arch/arm64/boot/dtb.img"
