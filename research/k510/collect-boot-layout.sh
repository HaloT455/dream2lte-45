#!/usr/bin/env bash
# Read-only device boot-layout inventory for Exynos8895; do not flash or write partitions.
set -euo pipefail
command -v adb >/dev/null || { echo "ADB missing" >&2; exit 2; }
[[ "$(adb devices | awk '$2=="device"{n++}END{print n+0}')" == 1 ]] || {
  echo "Connect EXACTLY ONE Android device with USB debugging" >&2; exit 3;
}
adb shell "su -c 'id'" | grep -q 'uid=0' || {
  echo "KernelSU root not available" >&2; exit 4;
}
OUTDIR="${K510_LAYOUT_OUTDIR:-$HOME/V12R5T_TEST}"
mkdir -p "$OUTDIR"
REPORT="$OUTDIR/k510-layout-$(date +%Y%m%d-%H%M%S).txt"
{
  echo '===== K510 P1D - READ ONLY BOOT LAYOUT ====='
  date -Is
  echo '===== KERNEL / HARDWARE ====='
  adb shell "su -c 'uname -a; cat /proc/device-tree/model 2>/dev/null'" | tr '\000' '\n'
  for p in ro.hardware ro.boot.hardware ro.boot.bootloader ro.boot.hw_rev ro.boot.revision ro.product.device; do
    printf '%s=' "$p"
    adb shell getprop "$p" | tr -d '\r'
  done
  echo '===== MEMORY MAP ====='
  adb shell "su -c 'cat /proc/iomem'" 2>&1 || true
  echo '===== DT LIVE MEMORY AND RESERVED-MEMORY REG CELLS (HEX BYTES) ====='
  adb shell "su -c 'for f in /proc/device-tree/memory@*/reg /proc/device-tree/reserved-memory/*/reg; do if [ -r \"\$f\" ]; then echo \"NODE=\$f\"; od -An -tx1 \"\$f\"; fi; done'" 2>&1 || true
  echo '===== RESERVED DT ROOT NODES ====='
  adb shell "su -c 'ls -la /proc/device-tree/reserved-memory 2>/dev/null'" 2>&1 || true
  echo '===== BOOT PARTITION PATHS - READ ONLY ====='
  adb shell "su -c 'ls -la /dev/block/by-name /dev/block/bootdevice/by-name 2>/dev/null'" 2>&1 || true
  echo '===== DT COMPATIBLE STRING ====='
  adb shell "su -c 'cat /proc/device-tree/compatible'" 2>/dev/null | tr '\000' '\n' || true
  echo '===== END ====='
} | tee "$REPORT"
echo "REPORT=$REPORT"
echo "Upload ONLY the text report; no serial/IMEI or raw firmware is collected."
echo "No kernel or partition changes were performed."
