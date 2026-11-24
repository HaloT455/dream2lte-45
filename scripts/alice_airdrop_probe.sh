#!/system/bin/sh
# Read-only capability report. Run from adb shell (root optional).
echo '=== ALice AirDrop feasibility probe ==='
getprop ro.product.model
getprop ro.build.version.release
uname -r
echo '=== Kernel features ==='
if [ -r /proc/config.gz ]; then
  zcat /proc/config.gz | grep -E '^(CONFIG_(BCM4361|WL_NAN|CFG80211|TUN|IPV6|PACKET|BT)=|# CONFIG_WL_NAN )'
else
  echo 'Kernel config unavailable'
fi
echo '=== Android feature declarations ==='
pm list features | grep -Ei 'wifi|bluetooth'
echo '=== Wi-Fi services ==='
service list | grep -Ei 'wifi|aware'
echo '=== Wi-Fi interfaces and driver ==='
for d in /sys/class/net/wlan*; do
  [ -d "$d" ] || continue
  echo "$d"
  readlink "$d/device/driver" 2>/dev/null
done
echo '=== Wi-Fi radio capabilities (if iw installed) ==='
if command -v iw >/dev/null 2>&1; then
  iw list 2>/dev/null | sed -n '/Supported interface modes:/,/Band [0-9]/p'
else
  echo 'iw unavailable; monitor and NAN capability not established'
fi
echo '=== Wi-Fi Aware service status (filtered) ==='
dumpsys wifiaware 2>/dev/null | grep -Ei 'available|supported|capabilities|usage enabled|not found' | head -n 30
echo '=== Quick Share package presence ==='
pm list packages | grep -Ei 'quickshare|nearby|com.google.android.gms|com.samsung.android.app.share'
echo 'Probe only: no radio settings, firmware, SELinux, or files changed.'

echo '=== NFC and Apple-link capabilities ==='
pm list features | grep -Ei 'android.hardware.nfc'
service list | grep -Ei 'nfc|wifi'
for iface in awdl0 mosey0; do
  if [ -d "/sys/class/net/$iface" ]; then echo "$iface present"; else echo "$iface absent now (not proof of lack of support)"; fi
done
echo 'No NFC settings or radio firmware changed.'

echo '=== Runtime Wi-Fi firmware and vendor HAL evidence ==='
if command -v lshal >/dev/null 2>&1; then lshal 2>/dev/null | grep -Ei 'android.hardware.wifi'; fi
service list | grep -Ei 'android.hardware.wifi|wifiaware'
for x in /sys/module/bcmdhd/version /sys/module/dhd/version; do [ ! -r "$x" ] || cat "$x"; done
# Root may be needed for dmesg. Filter to firmware/capability lines, no peer scans.
dmesg 2>/dev/null | grep -Ei 'Firmware version|FW version|firmware capability|fw_capabilities|NAN (supported|not supported)|AWDL (supported|not supported)|BCM4361' | tail -n 35
echo '=== Firmware and feature file names (no contents) ==='
for dir in /vendor/firmware /vendor/etc/wifi /system/etc/wifi /vendor/etc/permissions; do
 [ ! -d "$dir" ] || ls "$dir" 2>/dev/null | grep -Ei 'bcmdhd|4361|wifi.aware|wifi.direct|^fw_bcm'
done
