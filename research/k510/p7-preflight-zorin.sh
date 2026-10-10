#!/usr/bin/env bash
# P7 preflight for Zorin X270 + ADB + SM-G955F TWRP.
# READ-ONLY: no flash, reboot, remount, or any phone partition write.
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo "Usage: bash p7-preflight-zorin.sh /path/to/unpacked-P7-artifact /path/to/verified-V12R5T-BOOT.img" >&2
  exit 1
fi
DIR="$1"
STOCK="$2"
IMG="$DIR/Alice_K510_P7_SM-G955F_ANDROID_CORE_BOOT_GATE.img"
SUMS="$DIR/SHA256SUMS"
STOCK_HASH="76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823"
for bin in adb sha256sum stat; do command -v "$bin" >/dev/null || exit 10; done
test -r "$IMG" && test -r "$SUMS" && test -r "$STOCK"
[[ "$(stat -c %s "$IMG")" == 41943040 ]] || { echo "FAIL: P7 BOOT must be exactly 40 MiB" >&2; exit 1; }
[[ "$(stat -c %s "$STOCK")" == 41943040 ]] || { echo "FAIL: original BOOT must be exactly 40 MiB" >&2; exit 1; }
[[ "$(head -c 8 "$IMG")" == 'ANDROID!' ]] || { echo "FAIL: P7 BOOT header not ANDROID!" >&2; exit 1; }
echo "$STOCK_HASH  $STOCK" | sha256sum -c - || { echo "FAIL: V12R5T stock backup SHA differs; STOP!" >&2; exit 2; }
(cd "$DIR" && sha256sum -c "$(basename "$SUMS")") || { echo "FAIL: P7 image SHA differs; STOP!" >&2; exit 3; }
COUNT="$(adb devices | awk '$2=="device"{n++}END{print n+0}')"
[[ "$COUNT" == 1 ]] || { echo "FAIL: expected one adb-connected phone, got $COUNT" >&2; exit 4; }
MODEL="$(adb shell getprop ro.product.model | tr -d '\r')"
[[ "$MODEL" == "SM-G955F" ]] || { echo "FAIL: wrong model '$MODEL'" >&2; exit 5; }
BOOTPATH="$(adb shell 'readlink -f /dev/block/by-name/BOOT' | tr -d '\r')"
[[ -n "$BOOTPATH" && "$BOOTPATH" == /dev/block/* ]] || { echo "FAIL: BOOT alias missing ($BOOTPATH)" >&2; exit 6; }
KERNEL="$(adb shell uname -r | tr -d '\r')"
echo "Model=$MODEL recovery_kernel=$KERNEL BOOT=$BOOTPATH"
[[ "$KERNEL" == 4.4.* ]] || { echo "STOP: enter known-good TWRP kernel 4.4 first" >&2; exit 7; }
CAP="$(adb shell 'cat /sys/class/power_supply/battery/capacity' | tr -d '\r')"
[[ "$CAP" =~ ^[0-9]+$ ]] || { echo "Cannot read battery capacity: $CAP" >&2; exit 8; }
(( CAP >= 50 )) || { echo "STOP: battery only $CAP%; charge first" >&2; exit 9; }
echo "Battery=$CAP%"
echo "Current device BOOT SHA256 (read-only):"
adb shell 'sha256sum /dev/block/by-name/BOOT'
echo "Ramoops directory (read-only):"
adb shell 'ls -la /sys/fs/pstore 2>&1'
echo "PASS: OFFLINE FILE + TWRP DEVICE PREFLIGHT ONLY."
echo "Nothing was flashed. P7 BOOT IS UNVERIFIED AND MAY HANG/BLACKSCREEN."
echo "Keep Download Mode and a verified restore path available for a separate manual experiment."
