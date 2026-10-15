#!/system/bin/sh
# Finite CPU compatibility setup. Keep SF's original 0-7 eligibility; never edit root/cpus.
PATH=/system/bin:/system/xbin:/vendor/bin:/vendor/xbin:/sbin
export PATH
STATE=/data/adb/alice-cpu-compat
TARGET=/system/etc/task_profiles.json
GROUP=/dev/cpuset/sf
READY=/dev/alice-cpu-compat.ready
TOYBOX=/system/bin/toybox
OLD_SHA=6ddb7001e914c71755afe8bc0c964563d5735b63beec02eb450165c310df265f
NEW_SHA=f6a90f7a34e6e03cbb51e39bc380cbca9ea50d20ca7a6e9a1c47ef2bbaaa1085
umask 077
mkdir -p "$STATE" || exit 1
chmod 0700 "$STATE" || exit 1
exec >> "$STATE/status.log" 2>&1
echo "ALICE_CPU_COMPAT_R15 action=${1:-apply}"
[ ! -e "$STATE/disable" ] || { echo DISABLED; exit 0; }
case "${1:-apply}" in apply|join) ;; *) echo INVALID_ACTION; exit 1;; esac
# Android mksh predefines hash as an alias for its command-path cache.
# Use a unique function name: hash can return success with no digest.
alice_sha256() {
 line=$("$TOYBOX" sha256sum "$1" 2> "$STATE/hash-error.log") || line=
 if [ -z "$line" ]; then
  line=$(/system/bin/sha256sum "$1" 2>> "$STATE/hash-error.log") || {
   echo "HASH_READ_FAILED file=$1" >&2; return 1;
  }
 fi
 set -- $line
 h=${1:-}
 case "$h" in ''|*[!0-9a-f]*) echo HASH_OUTPUT_INVALID >&2; return 1;; esac
 [ "${#h}" -eq 64 ] || { echo HASH_OUTPUT_INVALID >&2; return 1; }
 printf '%s\n' "$h"
}
prepare_group() {
 [ "$(cat /dev/cpuset/cpus 2>/dev/null)" = 0-7 ] || { echo CPU_LAYOUT_SKIPPED; return 1; }
 MEMS=$(cat /dev/cpuset/mems 2>/dev/null)
 [ -n "$MEMS" ] || { echo CPUSET_MEMS_NOT_READY; return 1; }
 if [ ! -d "$GROUP" ]; then
  mkdir "$GROUP" || { echo SF_GROUP_CREATE_FAILED; return 1; }
  printf '%s\n' "$MEMS" > "$GROUP/mems" && printf '0-7\n' > "$GROUP/cpus" || { echo SF_GROUP_INIT_FAILED; return 1; }
  chown 1000:1000 "$GROUP" "$GROUP/cpus" "$GROUP/tasks" "$GROUP/cgroup.procs" &&
   chmod 0755 "$GROUP" && chmod 0664 "$GROUP/cpus" "$GROUP/tasks" "$GROUP/cgroup.procs" || { echo SF_GROUP_PERMISSIONS_FAILED; return 1; }
  printf 'ALICE_CPU_COMPAT_R15\n' > "$READY" || return 1
  echo SF_GROUP_CREATED
 fi
 # /dev is per-boot tmpfs: never take ownership of a foreign existing group.
 [ -r "$READY" ] && [ "$(cat "$READY" 2>/dev/null)" = ALICE_CPU_COMPAT_R15 ] || { echo SF_FOREIGN_GROUP_SKIPPED; return 1; }
 case "$(cat "$GROUP/cpus" 2>/dev/null)" in 0-7|4-7) ;; *) echo SF_GROUP_MASK_SKIPPED; return 1;; esac
 [ "$(cat "$GROUP/mems" 2>/dev/null)" = "$MEMS" ] || { echo SF_GROUP_MEMS_SKIPPED; return 1; }
 return 0
}
join_sf() {
 for pid in $(pidof surfaceflinger 2>/dev/null); do
  case "$pid" in ''|*[!0-9]*) continue;; esac
  [ "$(cat /proc/"$pid"/comm 2>/dev/null)" = surfaceflinger ] || continue
  uid= allowed= current=
  while read -r key value rest; do
   case "$key" in Uid:) uid=$value;; Cpus_allowed_list:) allowed=$value;; esac
  done < /proc/"$pid"/status
  [ "$uid" = 1000 ] || continue
  while IFS=: read -r ident controllers path; do
   case ",$controllers," in *,cpuset,*) current=$path;; esac
  done < /proc/"$pid"/cgroup
  [ "$current" != /sf ] || { echo "SF_ALREADY_JOINED pid=$pid"; continue; }
  # Preserve explicit ROM/task placement and CPU affinity. Only move root SF.
  [ "$current" = / ] && [ "$allowed" = 0-7 ] || { echo "SF_EXISTING_PLACEMENT_SKIPPED pid=$pid"; continue; }
  if printf '%s\n' "$pid" > "$GROUP/cgroup.procs"; then echo "SF_PROCESS_JOIN_REQUESTED pid=$pid";
  else echo SF_PROCESS_JOIN_FAILED; fi
 done
}
patch_profile() {
 CURRENT=$(alice_sha256 "$TARGET") || { echo PROFILE_READ_UNAVAILABLE_DEFERRED; return 0; }
 echo "PROFILE_SHA256=$CURRENT"
 case "$CURRENT" in
  "$NEW_SHA") echo PROFILE_ALREADY_FIXED; return 0;;
  "$OLD_SHA") ;;
  *) echo PROFILE_HASH_UNRECOGNIZED_SKIPPED; return 0;;
 esac
 TMP=$STATE/task_profiles.json.tmp
 awk '
 /"Name"[[:space:]]*:[[:space:]]*"GpisSfCpuset(Enable|Disable)"/ {active=1; profiles++}
 active && /"Name"[[:space:]]*:[[:space:]]*"SetAttribute"/ {sub(/"SetAttribute"/, "\"WriteFile\""); actions++}
 active && /"Name"[[:space:]]*:[[:space:]]*"GpisSfCpuset"/ {
  sub(/"Name"[[:space:]]*:[[:space:]]*"GpisSfCpuset"/, "\"FilePath\": \"/dev/cpuset/sf/cpus\""); paths++
 }
 active && /"Value"/ {active=0}
 {print}
 END {if (profiles != 2 || actions != 2 || paths != 2) exit 1}
 ' "$TARGET" > "$TMP" || { rm -f "$TMP"; echo PROFILE_PATCH_FAILED; return 0; }
 PATCHED=$(alice_sha256 "$TMP") || PATCHED=
 [ "$PATCHED" = "$NEW_SHA" ] || { rm -f "$TMP"; echo PATCH_HASH_FAILED; return 0; }
 set -- $(ls -Zd "$TARGET" 2>/dev/null)
 CONTEXT=${1:-}
 case "$CONTEXT" in u:object_r:*:s0) ;; *) rm -f "$TMP"; echo PROFILE_LABEL_UNKNOWN; return 0;; esac
 chmod 0644 "$TMP" && chown 0:0 "$TMP" && chcon "$CONTEXT" "$TMP" && mv "$TMP" "$STATE/task_profiles.json" || { rm -f "$TMP"; echo PATCH_PREPARE_FAILED; return 0; }
 if mount --bind "$STATE/task_profiles.json" "$TARGET"; then
  READBACK=$(alice_sha256 "$TARGET") || READBACK=
  if [ "$READBACK" = "$NEW_SHA" ]; then echo PROFILE_BOUND_GPIS_SF_ONLY;
  else umount "$TARGET"; echo MOUNT_READBACK_FAILED_ROLLBACK_REQUESTED; fi
 else echo PROFILE_BIND_FAILED; fi
}
prepare_group || exit 0
# Relative SetAttribute actions already cached by Android use the task's group.
# SF joining therefore does not depend on a JSON bind becoming visible in time.
patch_profile
join_sf
exit 0
