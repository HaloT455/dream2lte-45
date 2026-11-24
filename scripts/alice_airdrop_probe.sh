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
