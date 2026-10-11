#!/usr/bin/env bash
# P25 non-invasive baseline of WORKING Samsung S8+ 4.4 kernel.
# READS ONLY: never writes registers, boot partitions, props, EFS or userdata.
set -euo pipefail

ADB="${ADB:-adb}"
RUN="$(date +%Y%m%d_%H%M%S)"
OUT="${1:-$HOME/ALICE_K510_P25_READONLY_$RUN}"
mkdir -p "$OUT"
echo 'P25: collecting READ-ONLY device evidence; no writes and no flashing'

"$ADB" wait-for-device
if [ "$("$ADB" get-state)" != device ]; then
  echo 'P25 REFUSED: ADB device not connected' >&2
  exit 2
fi

# Selected hardware/build properties only; never request IMEI, serial,
# Android ID or app/userdata content.
"$ADB" shell '
for key in ro.product.model ro.product.device ro.hardware ro.board.platform            ro.build.version.release ro.build.version.sdk            ro.boot.bootreason ro.boot.verifiedbootstate            ro.boot.slot_suffix; do
    printf "%s=" "$key"
    getprop "$key"
done
uname -a
' > "$OUT/device-and-kernel.txt" 2>&1 || true

"$ADB" shell '
printf "=== UFS host nodes ===\n"
for path in /sys/class/ufs /sys/class/ufs_hba /sys/class/scsi_host; do
  if [ -d "$path" ]; then ls -l "$path"; fi
done
printf "\n=== UFS driver paths ===\n"
for path in /sys/bus/platform/drivers/ufshcd /sys/bus/platform/drivers/ufs-exynos; do
  if [ -d "$path" ]; then ls "$path"; fi
done
' > "$OUT/ufs-sysfs.txt" 2>&1 || true

"$ADB" shell '
printf "=== OF UFS-related node paths ===\n"
if [ -d /proc/device-tree ]; then
  find /proc/device-tree -maxdepth 5 -iname "*ufs*" 2>/dev/null | head -n 75
fi
printf "\n=== UFS IRQ lines ===\n"
if [ -r /proc/interrupts ]; then grep -i ufs /proc/interrupts || true; fi
' > "$OUT/of-and-interrupts.txt" 2>&1 || true

# Root-access logs are optional. This executes only read commands.
"$ADB" shell 'su -c "dmesg 2>/dev/null | grep -iE \"ufs|unipro|m-phy|acpm|s2mps17|fmp|smu\" | tail -n 350"'   > "$OUT/ufs-kernel-messages.txt" 2>&1 || true

"$ADB" shell 'su -c "cat /sys/kernel/debug/regulator/regulator_summary 2>/dev/null | grep -iE \"name|ufs|vcc|s2mps17\""'   > "$OUT/ufs-regulators.txt" 2>&1 || true

cat > "$OUT/README-NO-FLASH.txt" <<'EOF'
Read-only Exynos8895 V12R5T UFS/ACPM/clock baseline.
This capture neither validates the Linux 5.10 runtime nor backs up
the boot partition. No encryption keys, IMEI, userdata, or partition bytes
were deliberately requested. Review logs before sharing.
NEVER flash P23/P24/P25 research kernels.
EOF
(
  cd "$OUT"
  sha256sum *.txt > SHA256SUMS.txt
)
tar -C "$(dirname "$OUT")" -czf "$OUT.tar.gz" "$(basename "$OUT")"
echo "P25_READ_ONLY_LOG=$OUT.tar.gz"
