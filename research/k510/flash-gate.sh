#!/usr/bin/env bash
# K510 device-specific flash readiness checks; no modifications.
set -euo pipefail
TREE="${1:?Usage: $0 /path/to/genuine-linux-5.10}"
REPORT="${2:-k510-flash-readiness.txt}"
mkdir -p "$(dirname "$REPORT")"
status=0
{
 echo "Alice Exynos8895 K510 device boot readiness"
 date -u '+UTC %FT%TZ'
 if [[ ! -f "$TREE/Makefile" ]]; then
   echo "FAIL: missing source tree"
   exit 2
 fi
 KERNEL="$(make -s -C "$TREE" kernelversion)"
 echo "Kernel version: $KERNEL"
 if [[ "$KERNEL" != 5.10.* ]]; then echo "FAIL: not Linux 5.10"; status=1; fi
 for f in \
   arch/arm64/boot/dts/exynos/exynos8895.dtsi \
   arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts \
   arch/arm64/boot/dts/exynos/exynos8895-pinctrl.dtsi \
   drivers/clk/samsung/clk-exynos8895.c \
   include/dt-bindings/clock/samsung,exynos8895.h; do
   if [[ -s "$TREE/$f" ]]; then echo "PRESENT: $f"; else echo "MISSING: $f"; status=1; fi
 done
 if [[ -s "$TREE/arch/arm64/boot/Image" ]]; then
   echo "NOTE: in-tree Image exists, but not proof of device boot"
 fi
 echo
 echo "Additional independent proof REQUIRED before packaging:"
 echo "- dream2lte DTB build and binding validation, reserved memory / regulators"
 echo "- Exynos8895 clocks/pinctrl, early serial/pstore, storage and display drivers"
 echo "- Samsung bootloader shim/protocol, matching boot image parameters and vendor ramdisk"
 echo "- recovery path from bootloop; boot image must be clearly experimental"
 if (( status )); then
   echo "RESULT: BLOCKED -- NO BOOT.IMG MAY BE DISTRIBUTED AS FLASHABLE"
 else
   echo "RESULT: STATIC FILE GATE PASSED; NOT YET FLASH READY"
 fi
} | tee "$REPORT"
exit "$status"
