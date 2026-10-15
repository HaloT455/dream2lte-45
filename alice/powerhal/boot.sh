#!/system/bin/sh
# Install only over the audited public-service interface; vendor image is untouched.
STATE=/data/adb/alice-powerhal
TARGET=/vendor/bin/hw/android.hardware.power.samsung-service
NODE=/sys/power/alice_power_hint
BLOB=/sys/kernel/alice_powerhal
OLD_SHA=004d0fc5dd5e91a8bf423f1fa0def109b0374b3f7cf5e6deedbf319c8e5780bc
umask 077
mkdir -p "$STATE" || exit 1
chmod 0700 "$STATE" || exit 1
exec >> "$STATE/status.log" 2>&1
echo ALICE_POWERHAL_R12
hash() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
if [ "${1:-apply}" = guard ]; then
 [ "$(hash "$TARGET")" = "$(hash "$BLOB")" ] || exit 0
 tries=0
 while [ "$tries" -lt 6 ]; do
  if dumpsys -t 1 android.hardware.power.IPower/default 2>/dev/null | grep -q 'backend=ready'; then
   echo POWERHAL_RUNTIME_READY
   exit 0
  fi
  tries=$((tries + 1))
  sleep 1
 done
 if umount "$TARGET" && [ "$(hash "$TARGET")" = "$OLD_SHA" ]; then
  printf 'reset\n' > "$NODE"
  touch "$STATE/disable"
  echo POWERHAL_FALLBACK_VENDOR_RESTORED
  setprop ctl.restart vendor.samsung.power-default
 else echo POWERHAL_FALLBACK_UNMOUNT_FAILED; fi
 exit 0
fi
[ ! -e "$STATE/disable" ] || { echo DISABLED; exit 0; }
[ "$(hash "$TARGET")" = "$OLD_SHA" ] || { echo VENDOR_HASH_UNKNOWN_SKIPPED; exit 0; }
[ -r "$BLOB" ] && [ -w "$NODE" ] || { echo KERNEL_BACKEND_MISSING; exit 0; }
# Fail closed if the ROM moved its active HAL to another process/interface.
grep -q 'android.hardware.power.samsung-service' /vendor/etc/init/power-default-sec.rc &&
 grep -q '<version>2</version>' /vendor/etc/vintf/manifest/power-samsung.xml || { echo SERVICE_LAYOUT_UNKNOWN; exit 0; }
CONTEXT=$(ls -Zd "$TARGET" 2>/dev/null | awk '{print $1}')
[ "$CONTEXT" = u:object_r:hal_power_default_exec:s0 ] || { echo EXEC_LABEL_UNKNOWN; exit 0; }
LABEL=$(ls -Zd /sys/power/cpufreq_min_limit 2>/dev/null | awk '{print $1}')
case "$LABEL" in u:object_r:sysfs_power*:s0) ;; *) echo QOS_LABEL_UNKNOWN; exit 0;; esac
cat "$BLOB" > "$STATE/service.tmp" || { echo COPY_FAILED; exit 0; }
[ -s "$STATE/service.tmp" ] && [ "$(hash "$STATE/service.tmp")" = "$(hash "$BLOB")" ] || { rm -f "$STATE/service.tmp"; echo COPY_HASH_FAILED; exit 0; }
chmod 0755 "$STATE/service.tmp" && chown 0:0 "$STATE/service.tmp" &&
 chcon "$CONTEXT" "$STATE/service.tmp" &&
 chown 1000:1000 "$NODE" && chmod 0660 "$NODE" && chcon "$LABEL" "$NODE" &&
 mv "$STATE/service.tmp" "$STATE/service" || { rm -f "$STATE/service.tmp"; echo PREPARE_FAILED; exit 0; }
if mount --bind "$STATE/service" "$TARGET"; then
 if [ "$(hash "$TARGET")" = "$(hash "$BLOB")" ]; then
  echo POWERHAL_BOUND
  ls -lZ "$TARGET" "$NODE"
 else
  umount "$TARGET"
  echo READBACK_FAILED_ROLLBACK_REQUESTED
 fi
else echo BIND_FAILED; fi
exit 0
