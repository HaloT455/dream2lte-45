#!/system/bin/sh
# Hash-checked early install with one finite retry after Android is ready.
PATH=/system/bin:/system/xbin:/vendor/bin:/vendor/xbin:/sbin
export PATH
STATE=/data/adb/alice-powerhal
TARGET=/vendor/bin/hw/android.hardware.power.samsung-service
NODE=/sys/power/alice_power_hint
BLOB=/sys/kernel/alice_powerhal
MOUNTINFO=/proc/self/mountinfo
BOOT_ID_FILE=/proc/sys/kernel/random/boot_id
LOCK=/dev/alice-powerhal.lock
TOYBOX=/system/bin/toybox
OLD_SHA=004d0fc5dd5e91a8bf423f1fa0def109b0374b3f7cf5e6deedbf319c8e5780bc
umask 077
mkdir -p "$STATE" || exit 1
chmod 0700 "$STATE" || exit 1
exec >> "$STATE/status.log" 2>&1
echo "ALICE_POWERHAL_R13 action=${1:-apply}"
mkdir "$LOCK" 2>/dev/null || { echo INSTALL_BUSY; exit 0; }
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
trap 'exit 1' HUP INT TERM

hash() {
 # Explicit tool path and validated output: failed reads can never compare equal.
 line=$("$TOYBOX" sha256sum "$1" 2> "$STATE/hash-error.log") || line=
 if [ -z "$line" ]; then
  line=$(/system/bin/sha256sum "$1" 2>> "$STATE/hash-error.log") || {
  echo "HASH_READ_FAILED file=$1" >&2
  cat "$STATE/hash-error.log" >&2
  return 1
  }
 fi
 set -- $line
 h=${1:-}
 case "$h" in ''|*[!0-9a-f]*) echo HASH_OUTPUT_INVALID >&2; return 1;; esac
 [ "${#h}" -eq 64 ] || { echo HASH_OUTPUT_INVALID >&2; return 1; }
 printf '%s\n' "$h"
}

mount_id() {
 while read -r ident parent device root point options rest; do
  [ "$point" = "$TARGET" ] && printf '%s\n' "$ident"
 done < "$MOUNTINFO"
 return 0
}

own_mount() {
 [ -r "$STATE/bound" ] || return 1
 read -r recorded_boot recorded_mount recorded_sha < "$STATE/bound" || return 1
 [ -n "$recorded_boot" ] && [ "$recorded_boot" = "$BOOT_ID" ] || return 1
 [ -n "$recorded_mount" ] && [ "$recorded_mount" = "$(mount_id)" ] || return 1
 [ -n "$recorded_sha" ] && [ "$recorded_sha" = "$PAYLOAD_SHA" ] || return 1
 [ -n "$CURRENT_SHA" ] && [ "$CURRENT_SHA" = "$PAYLOAD_SHA" ]
}

install_payload() {
 [ "$CURRENT_SHA" != "$PAYLOAD_SHA" ] || { echo UNOWNED_REPLACEMENT_SKIPPED; return 1; }
 [ "$CURRENT_SHA" = "$OLD_SHA" ] || { echo "VENDOR_HASH_UNKNOWN_SKIPPED observed=$CURRENT_SHA"; return 1; }
 [ -z "$(mount_id)" ] || { echo TARGET_ALREADY_MOUNTED_SKIPPED; return 1; }
 [ -w "$NODE" ] || { echo KERNEL_BACKEND_MISSING; return 1; }
 grep -q 'android.hardware.power.samsung-service' /vendor/etc/init/power-default-sec.rc &&
  grep -q '<version>2</version>' /vendor/etc/vintf/manifest/power-samsung.xml || { echo SERVICE_LAYOUT_UNKNOWN; return 1; }
 set -- $(ls -Zd "$TARGET" 2>/dev/null)
 CONTEXT=${1:-}
 [ "$CONTEXT" = u:object_r:hal_power_default_exec:s0 ] || { echo EXEC_LABEL_UNKNOWN; return 1; }
 set -- $(ls -Zd /sys/power/cpufreq_min_limit 2>/dev/null)
 LABEL=${1:-}
 case "$LABEL" in u:object_r:sysfs_power*:s0) ;; *) echo QOS_LABEL_UNKNOWN; return 1;; esac
 cat "$BLOB" > "$STATE/service.tmp" || { echo COPY_FAILED; return 1; }
 COPIED_SHA=$(hash "$STATE/service.tmp") || { rm -f "$STATE/service.tmp"; return 1; }
 [ "$COPIED_SHA" = "$PAYLOAD_SHA" ] || { rm -f "$STATE/service.tmp"; echo COPY_HASH_FAILED; return 1; }
 chmod 0755 "$STATE/service.tmp" && chown 0:0 "$STATE/service.tmp" &&
  chcon "$CONTEXT" "$STATE/service.tmp" &&
  chown 1000:1000 "$NODE" && chmod 0660 "$NODE" && chcon "$LABEL" "$NODE" &&
  mv "$STATE/service.tmp" "$STATE/service" || { rm -f "$STATE/service.tmp"; echo PREPARE_FAILED; return 1; }
 mount --bind "$STATE/service" "$TARGET" || { echo BIND_FAILED; return 1; }
 INSTALLED_MOUNT=$(mount_id)
 CURRENT_SHA=$(hash "$TARGET") || CURRENT_SHA=
 if [ -n "$INSTALLED_MOUNT" ] && [ "$CURRENT_SHA" = "$PAYLOAD_SHA" ]; then
  printf '%s %s %s\n' "$BOOT_ID" "$INSTALLED_MOUNT" "$PAYLOAD_SHA" > "$STATE/bound.tmp" &&
   mv "$STATE/bound.tmp" "$STATE/bound" || {
    umount -l "$TARGET"
    echo BIND_RECORD_FAILED
    return 1
   }
  echo "POWERHAL_BOUND mount=$INSTALLED_MOUNT"
  ls -lZ "$TARGET" "$NODE"
  return 0
 fi
 # This invocation just created the mount; detach only that same mount ID.
 if [ -n "$INSTALLED_MOUNT" ] && [ "$(mount_id)" = "$INSTALLED_MOUNT" ]; then
  umount -l "$TARGET"
 fi
 echo READBACK_FAILED_ROLLBACK_REQUESTED
 return 1
}

rollback_owned() {
 CURRENT_SHA=$(hash "$TARGET") || { echo FALLBACK_HASH_UNREADABLE_SKIPPED; return 1; }
 own_mount || { echo FALLBACK_UNOWNED_MOUNT_SKIPPED; return 1; }
 umount -l "$TARGET" || { echo POWERHAL_FALLBACK_UNMOUNT_FAILED; return 1; }
 RESTORED_SHA=$(hash "$TARGET") || { echo FALLBACK_READBACK_FAILED; return 1; }
 [ "$RESTORED_SHA" = "$OLD_SHA" ] || { echo FALLBACK_VENDOR_CHANGED_SKIPPED; return 1; }
 rm -f "$STATE/bound"
 printf 'reset\n' > "$NODE"
 touch "$STATE/disable"
 echo POWERHAL_FALLBACK_VENDOR_RESTORED
 /system/bin/setprop ctl.restart vendor.samsung.power-default
}

case "${1:-apply}" in apply|guard) ;; *) echo INVALID_ACTION; exit 1;; esac
[ ! -e "$STATE/disable" ] || { echo DISABLED; exit 0; }
read -r BOOT_ID < "$BOOT_ID_FILE" || { echo BOOT_ID_UNAVAILABLE_DEFERRED; exit 0; }
[ -n "$BOOT_ID" ] || { echo BOOT_ID_UNAVAILABLE_DEFERRED; exit 0; }
CURRENT_SHA=$(hash "$TARGET") || { echo VENDOR_NOT_READABLE_DEFERRED; exit 0; }
PAYLOAD_SHA=$(hash "$BLOB") || { echo PAYLOAD_NOT_READABLE_DEFERRED; exit 0; }
[ -n "$CURRENT_SHA" ] && [ -n "$PAYLOAD_SHA" ] || { echo HASH_NOT_READY_DEFERRED; exit 0; }
[ "$PAYLOAD_SHA" != "$OLD_SHA" ] || { echo PAYLOAD_INVALID_SKIPPED; exit 0; }

INSTALLED_NOW=0
if own_mount; then
 echo POWERHAL_ALREADY_BOUND
else
 install_payload || exit 0
 INSTALLED_NOW=1
fi
[ "${1:-apply}" = guard ] || exit 0

# Late retries run through init's existing guard service, avoiding an adb shell's
# private mount namespace. Restart the vendor service only after an owned bind.
if [ "$INSTALLED_NOW" = 1 ]; then
 echo POWERHAL_LATE_INSTALL_RESTART
 /system/bin/setprop ctl.restart vendor.samsung.power-default
fi
tries=0
while [ "$tries" -lt 6 ]; do
 if /system/bin/dumpsys -t 1 android.hardware.power.IPower/default 2>/dev/null | grep -q 'backend=ready'; then
  echo POWERHAL_RUNTIME_READY
  exit 0
 fi
 tries=$((tries + 1))
 sleep 1
done
rollback_owned
exit 0
