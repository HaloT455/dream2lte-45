#!/system/bin/sh
# Finite post-fs-data compatibility fix for the audited One UI task profiles.
STATE=/data/adb/alice-cpu-compat
TARGET=/system/etc/task_profiles.json
GROUP=/dev/cpuset/sf
OLD_SHA=6ddb7001e914c71755afe8bc0c964563d5735b63beec02eb450165c310df265f
NEW_SHA=f6a90f7a34e6e03cbb51e39bc380cbca9ea50d20ca7a6e9a1c47ef2bbaaa1085
umask 077
mkdir -p "$STATE" || exit 1
chmod 0700 "$STATE" || exit 1
exec >> "$STATE/status.log" 2>&1
echo "ALICE_CPU_COMPAT_R11 action=${1:-apply}"
[ ! -e "$STATE/disable" ] || { echo DISABLED; exit 0; }
hash() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }

join_sf() {
 [ "$(hash "$TARGET")" = "$NEW_SHA" ] || { echo SF_JOIN_PROFILE_NOT_READY; return 0; }
 [ -w "$GROUP/cgroup.procs" ] || { echo SF_JOIN_GROUP_NOT_READY; return 0; }
 for pid in $(pidof surfaceflinger 2>/dev/null); do
  case "$pid" in ''|*[!0-9]*) continue;; esac
  [ "$(cat /proc/"$pid"/comm 2>/dev/null)" = surfaceflinger ] || continue
  uid=$(awk '/^Uid:/ {print $2}' /proc/"$pid"/status 2>/dev/null)
  [ "$uid" = 1000 ] || continue
  if printf '%s\n' "$pid" > "$GROUP/cgroup.procs"; then
   echo "SF_PROCESS_JOIN_REQUESTED pid=$pid"
  else echo SF_PROCESS_JOIN_FAILED; fi
 done
}

case "${1:-apply}" in
 join) join_sf; exit 0;;
 apply) ;;
 *) echo INVALID_ACTION; exit 1;;
esac

CURRENT=$(hash "$TARGET")
case "$CURRENT" in
 "$OLD_SHA"|"$NEW_SHA") ;;
 *) echo PROFILE_HASH_UNRECOGNIZED_SKIPPED; exit 0;;
esac
[ "$(cat /dev/cpuset/cpus 2>/dev/null)" = 0-7 ] || { echo CPU_LAYOUT_SKIPPED; exit 0; }
MEMS=$(cat /dev/cpuset/mems 2>/dev/null)
[ -n "$MEMS" ] || { echo CPUSET_MEMS_NOT_READY; exit 0; }
if [ ! -d "$GROUP" ]; then
 mkdir "$GROUP" || { echo SF_GROUP_CREATE_FAILED; exit 0; }
 printf '%s\n' "$MEMS" > "$GROUP/mems" &&
 printf '0-7\n' > "$GROUP/cpus" || { echo SF_GROUP_INIT_FAILED; exit 0; }
fi
[ -n "$(cat "$GROUP/cpus" 2>/dev/null)" ] &&
 [ -n "$(cat "$GROUP/mems" 2>/dev/null)" ] || { echo SF_GROUP_EMPTY_SKIPPED; exit 0; }
chown 1000:1000 "$GROUP" "$GROUP/cpus" "$GROUP/tasks" "$GROUP/cgroup.procs" &&
 chmod 0755 "$GROUP" &&
 chmod 0664 "$GROUP/cpus" "$GROUP/tasks" "$GROUP/cgroup.procs" || { echo SF_GROUP_PERMISSIONS_FAILED; exit 0; }

if [ "$CURRENT" = "$NEW_SHA" ]; then
 echo PROFILE_ALREADY_FIXED
 join_sf
 exit 0
fi

# Only two GPIS actions change. Absolute WriteFile paths work regardless of
# the target task's current cpuset; relative SetAttribute paths do not.
TMP=$STATE/task_profiles.json.tmp
awk '
 /"Name"[[:space:]]*:[[:space:]]*"GpisSfCpuset(Enable|Disable)"/ {active=1; profiles++}
 active && /"Name"[[:space:]]*:[[:space:]]*"SetAttribute"/ {
  sub(/"SetAttribute"/, "\"WriteFile\""); actions++
 }
 active && /"Name"[[:space:]]*:[[:space:]]*"GpisSfCpuset"/ {
  sub(/"Name"[[:space:]]*:[[:space:]]*"GpisSfCpuset"/, "\"FilePath\": \"/dev/cpuset/sf/cpus\""); paths++
 }
 active && /"Value"/ {active=0}
 {print}
 END {if (profiles != 2 || actions != 2 || paths != 2) exit 1}
' "$TARGET" > "$TMP" || { rm -f "$TMP"; echo PROFILE_PATCH_FAILED; exit 0; }
[ "$(hash "$TMP")" = "$NEW_SHA" ] || { rm -f "$TMP"; echo PATCH_HASH_FAILED; exit 0; }
CONTEXT=$(ls -Zd "$TARGET" 2>/dev/null | awk '{print $1}')
case "$CONTEXT" in u:object_r:*:s0) ;; *) rm -f "$TMP"; echo PROFILE_LABEL_UNKNOWN; exit 0;; esac
chmod 0644 "$TMP" && chown 0:0 "$TMP" &&
 chcon "$CONTEXT" "$TMP" &&
 mv "$TMP" "$STATE/task_profiles.json" || { rm -f "$TMP"; echo PATCH_PREPARE_FAILED; exit 0; }
if mount --bind "$STATE/task_profiles.json" "$TARGET"; then
 if [ "$(hash "$TARGET")" = "$NEW_SHA" ]; then
  echo PROFILE_BOUND_GPIS_SF_ONLY
  join_sf
 else
  umount "$TARGET"
  echo MOUNT_READBACK_FAILED_ROLLBACK_REQUESTED
 fi
else echo PROFILE_BIND_FAILED; fi
exit 0
