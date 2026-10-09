#!/usr/bin/env bash
# P2A: sandbox build of upstream uniLoader using the SM-G950F board target.
# This is NOT yet an adapted SM-G955F loader and SHALL NEVER be flashed.
set -euo pipefail
SRC="$1"
DTB="$2"
RAMDISK="$3"
WORK="$4"
PIN=1144a9ff7fc9e99ca7f52433f4a02847b44b7051
test -s "$SRC"
test -s "$DTB"
test -s "$RAMDISK"
mkdir -p "$WORK"
if [[ ! -d "$WORK/uniLoader/.git" ]]; then
    git init -q "$WORK/uniLoader"
    git -C "$WORK/uniLoader" remote add origin https://github.com/ivoszbg/uniLoader.git
    git -C "$WORK/uniLoader" fetch --depth=1 origin "$PIN"
    git -C "$WORK/uniLoader" checkout -q --detach "$PIN"
fi
[[ "$(git -C "$WORK/uniLoader" rev-parse HEAD)" == "$PIN" ]] || {
    echo 'Unexpected uniLoader source revision' >&2; exit 4;
}
cd "$WORK/uniLoader"
mkdir -p blob
cp "$SRC" blob/Image
cp "$DTB" blob/dtb
cp "$RAMDISK" blob/ramdisk
# Verified upstream only has dreamlte board config: NOT dream2lte.
# Compile to identify integration/toolchain/linker blockers.
make ARCH=aarch64 CROSS_COMPILE=aarch64-linux-gnu- dreamlte_defconfig
grep -q '^CONFIG_LIBFDT=y' .config
grep -q '^CONFIG_SAMSUNG_DREAMLTE=y' .config
make ARCH=aarch64 CROSS_COMPILE=aarch64-linux-gnu- -j2
test -s uniLoader
aarch64-linux-gnu-objdump -f uniLoader.o | grep -q 'aarch64'
sha256sum uniLoader blob/Image blob/dtb blob/ramdisk > "$WORK/uniloader-lab-sha256.txt"
echo 'Upstream uniLoader compiled with dreamlte target; this is NOT SM-G955F handoff validation.'
echo 'NOT A BOOT IMAGE. NEVER FLASH.'
