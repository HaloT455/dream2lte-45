#!/usr/bin/env bash
# P2C: combine P2B SM-G955F compiler-tested board with real Linux 5.10.
# Board PMIC/DECON writes disabled. Real bootloader handoff NOT validated.
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
# Adapt donor SM-G950F board into explicit compiler-tested SM-G955F profile.
# P2B disabled unverified DECON and PMIC writes.
bash "$OLDPWD/research/k510/p2-adapt-uniloader-dream2lte.sh" . "$SRC"
if [[ "${ALICE_K510_P8_COPY_CHECK:-0}" == "1" ]]; then
    python3 "$OLDPWD/research/k510/p8-instrument-uniloader-handoff.py" .
fi
if [[ "${ALICE_K510_P9_CPU_PROBE:-0}" == "1" ]]; then
    python3 "$OLDPWD/research/k510/p9-probe-cpu-entry.py" .
fi
if [[ "${ALICE_K510_P10_FIX_HANDOFF:-0}" == "1" ]]; then
    python3 "$OLDPWD/research/k510/p10-fix-arm64-handoff.py" .
fi
mkdir -p blob
cp "$SRC" blob/Image
cp "$DTB" blob/dtb
cp "$RAMDISK" blob/ramdisk
# Verified upstream only has dreamlte board config: NOT dream2lte.
# Compile to identify integration/toolchain/linker blockers.
make ARCH=aarch64 CROSS_COMPILE=aarch64-linux-gnu- dream2lte_defconfig
grep -q '^CONFIG_LIBFDT=y' .config
grep -q '^CONFIG_SAMSUNG_DREAM2LTE=y' .config
make ARCH=aarch64 CROSS_COMPILE=aarch64-linux-gnu- -j2
test -s uniLoader
aarch64-linux-gnu-objdump -f uniLoader.o | grep -q 'aarch64'
sha256sum uniLoader blob/Image blob/dtb blob/ramdisk > "$WORK/uniloader-lab-sha256.txt"
echo 'uniLoader compiled with experimental SM-G955F dream2lte target; hardware handoff NOT verified.'
echo 'NOT A BOOT IMAGE. NEVER FLASH.'
