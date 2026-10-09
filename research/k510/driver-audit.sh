#!/usr/bin/env bash
# Read-only inventory of old Exynos8895 downstream vs genuine Linux 5.10 source.
set -euo pipefail
OLD="${1:-.}"
NEW="${2:-${K510_WORKDIR:-$HOME/alice-k510}/linux-5.10.262}"
[[ -f "$OLD/Makefile" && -f "$NEW/Makefile" ]] || {
  echo "Usage: bash $0 /path/to/dream2lte-4.4 /path/to/linux-5.10.262" >&2; exit 2;
}
OLD="$(cd "$OLD" && pwd)"
NEW="$(cd "$NEW" && pwd)"
OLD_V="$(make -s -C "$OLD" kernelversion)"
NEW_V="$(make -s -C "$NEW" kernelversion)"
[[ "$OLD_V" == 4.4.* && "$NEW_V" == 5.10.* ]] || {
  echo "WARNING: expected 4.4.x and 5.10.x sources, found $OLD_V and $NEW_V" >&2; exit 3;
}
OUT="${K510_WORKDIR:-$HOME/alice-k510}/reports"
mkdir -p "$OUT"
REPORT="$OUT/exynos8895-port-inventory.txt"
{
  echo "Exynos8895/dream2lte K510 P0 read-only audit"
  date -Is
  echo "Downstream: $OLD ($OLD_V)"
  echo "Upstream: $NEW ($NEW_V)"
  echo
  echo "[Downstream device-tree candidates]"
  find "$OLD/arch/arm64/boot/dts/exynos" -maxdepth 1 -type f \
    \( -iname '*dream2*' -o -iname '*8895*' \) -printf '%f\n' | sort | head -80
  echo
  echo "[Upstream Exynos8895 device-tree candidates]"
  find "$NEW/arch/arm64/boot/dts/exynos" -maxdepth 1 -type f \
    \( -iname '*dream2*' -o -iname '*8895*' \) -printf '%f\n' | sort | head -80
  echo
  echo "[Subsystem file counts — counts do NOT imply compatibility]"
  for p in drivers/gpu drivers/media drivers/video drivers/usb drivers/clk drivers/pinctrl drivers/mmc drivers/net/wireless sound drivers/thermal; do
    old_n=0; new_n=0
    if [[ -d "$OLD/$p" ]]; then old_n="$(find "$OLD/$p" -type f | wc -l)"; fi
    if [[ -d "$NEW/$p" ]]; then new_n="$(find "$NEW/$p" -type f | wc -l)"; fi
    printf '%-27s  old=%-7s new=%-7s\n' "$p" "$old_n" "$new_n"
  done
  echo
  echo "Port gates: exact dream2lte DT + reserved memory + clocks/regulators + boot shim"
  echo "Then persistent logs, storage, display/touch, thermal/power, GPU, modem, camera, vendor/HAL"
  echo "NO FLASHABLE OUTPUT"
} | tee "$REPORT"
echo "Report saved: $REPORT"
