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
echo "ALICE_POWERHAL_R16 action=${1:-apply}"
mkdir "$LOCK" 2>/dev/null || { echo INSTALL_BUSY; exit 0; }
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
trap 'exit 1' HUP INT TERM

# Android mksh predefines hash as an alias for its command-path cache.
# Use a unique function name: hash can return success with no digest.
alice_sha256() {
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
  [ "$point" = "$MOUNT_POINT" ] && printf '%s\n' "$ident"
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
 COPIED_SHA=$(alice_sha256 "$STATE/service.tmp") || { rm -f "$STATE/service.tmp"; return 1; }
 [ "$COPIED_SHA" = "$PAYLOAD_SHA" ] || { rm -f "$STATE/service.tmp"; echo COPY_HASH_FAILED; return 1; }
 chmod 0755 "$STATE/service.tmp" && chown 0:0 "$STATE/service.tmp" &&
  chcon "$CONTEXT" "$STATE/service.tmp" &&
  chown 1000:1000 "$NODE" && chmod 0660 "$NODE" && chcon "$LABEL" "$NODE" &&
  mv "$STATE/service.tmp" "$STATE/service" || { rm -f "$STATE/service.tmp"; echo PREPARE_FAILED; return 1; }
 mount --bind "$STATE/service" "$TARGET" || { echo BIND_FAILED; return 1; }
 INSTALLED_MOUNT=$(mount_id)
 CURRENT_SHA=$(alice_sha256 "$TARGET") || CURRENT_SHA=
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
 CURRENT_SHA=$(alice_sha256 "$TARGET") || { echo FALLBACK_HASH_UNREADABLE_SKIPPED; return 1; }
 own_mount || { echo FALLBACK_UNOWNED_MOUNT_SKIPPED; return 1; }
 umount -l "$TARGET" || { echo POWERHAL_FALLBACK_UNMOUNT_FAILED; return 1; }
 RESTORED_SHA=$(alice_sha256 "$TARGET") || { echo FALLBACK_READBACK_FAILED; return 1; }
 [ "$RESTORED_SHA" = "$OLD_SHA" ] || { echo FALLBACK_VENDOR_CHANGED_SKIPPED; return 1; }
 rm -f "$STATE/bound"
 printf 'reset\n' > "$NODE"
 # Automatic failure belongs to this payload; the separate disable file stays
 # an explicit user/legacy opt-out and is never deleted by this script.
 printf 'ALICE_POWERHAL_R16 %s\n' "$PAYLOAD_SHA" > "$STATE/auto-disabled.tmp" &&
  mv "$STATE/auto-disabled.tmp" "$STATE/auto-disabled" || echo AUTO_DISABLE_RECORD_FAILED
 echo POWERHAL_FALLBACK_VENDOR_RESTORED
 /system/bin/setprop ctl.restart vendor.samsung.power-default
}

payload_running() {
 for pid in $(/system/bin/pidof android.hardware.power.samsung-service 2>/dev/null); do
  case "$pid" in ''|*[!0-9]*) continue;; esac
  RUNNING_SHA=$(alice_sha256 /proc/"$pid"/exe) || continue
  [ "$RUNNING_SHA" = "$PAYLOAD_SHA" ] && return 0
 done
 return 1
}

health_probe() {
 if /system/bin/dumpsys -t 1 android.hardware.power.IPower/default > "$STATE/health-last.log" 2>&1; then
  HEALTH_RC=0
 else HEALTH_RC=$?; fi
 [ "$HEALTH_RC" = 0 ] &&
  grep -Fq 'ALICE Power HAL R16 AIDL V2; backend=ready;' "$STATE/health-last.log" && payload_running
}

restart_owned_once() {
 CURRENT_SHA=$(alice_sha256 "$TARGET") || return 1
 own_mount || { echo RESTART_UNOWNED_MOUNT_SKIPPED; return 1; }
 attempt_boot= attempt_mount= attempt_sha=
 if [ -r "$STATE/restart-attempt" ]; then
  read -r attempt_boot attempt_mount attempt_sha < "$STATE/restart-attempt"
 fi
 if [ "$attempt_boot" = "$BOOT_ID" ] && [ "$attempt_mount" = "$(mount_id)" ] &&
    [ "$attempt_sha" = "$PAYLOAD_SHA" ]; then
  echo POWERHAL_RESTART_ALREADY_REQUESTED
  return 0
 fi
 printf '%s %s %s\n' "$BOOT_ID" "$(mount_id)" "$PAYLOAD_SHA" > "$STATE/restart-attempt.tmp" &&
  mv "$STATE/restart-attempt.tmp" "$STATE/restart-attempt" || { echo RESTART_RECORD_FAILED; return 1; }
 echo POWERHAL_OWNED_BIND_RESTART
 /system/bin/setprop ctl.restart vendor.samsung.power-default || { echo RESTART_REQUEST_FAILED; return 1; }
}

save_failure() {
 {
  echo "ALICE_POWERHAL_R16 health_rc=$HEALTH_RC payload_sha=$PAYLOAD_SHA"
  /system/bin/getprop init.svc.vendor.samsung.power-default
  for pid in $(/system/bin/pidof android.hardware.power.samsung-service 2>/dev/null); do
   case "$pid" in ''|*[!0-9]*) continue;; esac
   echo "PROCESS pid=$pid"
   alice_sha256 /proc/"$pid"/exe
  done
  echo HEALTH_OUTPUT
  cat "$STATE/health-last.log"
  echo KERNEL_BACKEND
  cat "$NODE"
  echo FILTERED_STARTUP_LOG
  /system/bin/timeout 2 /system/bin/logcat -d -b all -t 600 -v threadtime 2>&1 |
   grep -Ei 'AlicePower|CANNOT LINK EXECUTABLE.*power|linker.*power|avc:.*(hal_power|alice_power)|init.*(power-default|power.samsung)' |
   tail -60
 } > "$STATE/diagnostic-last.log" 2>&1
 echo POWERHAL_FAILURE_DIAGNOSTIC_SAVED
}

case "${1:-apply}" in apply|guard) ;; *) echo INVALID_ACTION; exit 1;; esac
[ ! -e "$STATE/disable" ] || { echo DISABLED; exit 0; }
read -r BOOT_ID < "$BOOT_ID_FILE" || { echo BOOT_ID_UNAVAILABLE_DEFERRED; exit 0; }
[ -n "$BOOT_ID" ] || { echo BOOT_ID_UNAVAILABLE_DEFERRED; exit 0; }
# mountinfo reports the resolved mountpoint even when /vendor is a symlink.
MOUNT_POINT=$("$TOYBOX" readlink -f "$TARGET") || { echo TARGET_PATH_NOT_READY_DEFERRED; exit 0; }
[ -n "$MOUNT_POINT" ] && [ -f "$MOUNT_POINT" ] || { echo TARGET_PATH_NOT_READY_DEFERRED; exit 0; }
CURRENT_SHA=$(alice_sha256 "$TARGET") || { echo VENDOR_NOT_READABLE_DEFERRED; exit 0; }
PAYLOAD_SHA=$(alice_sha256 "$BLOB") || { echo PAYLOAD_NOT_READABLE_DEFERRED; exit 0; }
[ -n "$CURRENT_SHA" ] && [ -n "$PAYLOAD_SHA" ] || { echo HASH_NOT_READY_DEFERRED; exit 0; }
[ "$PAYLOAD_SHA" != "$OLD_SHA" ] || { echo PAYLOAD_INVALID_SKIPPED; exit 0; }
auto_version= auto_sha=
if [ -r "$STATE/auto-disabled" ]; then
 read -r auto_version auto_sha < "$STATE/auto-disabled"
 if [ "$auto_version" = ALICE_POWERHAL_R16 ] && [ "$auto_sha" = "$PAYLOAD_SHA" ]; then
  echo PAYLOAD_AUTOMATICALLY_DISABLED
  exit 0
 fi
fi

if own_mount; then
 echo POWERHAL_ALREADY_BOUND
else
 install_payload || exit 0
fi
[ "${1:-apply}" = guard ] || exit 0

# Pathname verification alone cannot prove which executable init already ran.
# A healthy replacement needs no restart. Otherwise request at most one restart
# for this verified current-boot bind, including binds made by the early action.
if health_probe; then
 echo POWERHAL_RUNTIME_READY
 exit 0
fi
restart_owned_once || { save_failure; rollback_owned; exit 0; }
tries=0
while [ "$tries" -lt 8 ]; do
 if health_probe; then
  echo POWERHAL_RUNTIME_READY
  exit 0
 fi
 tries=$((tries + 1))
 sleep 1
done
save_failure
rollback_owned
exit 0
