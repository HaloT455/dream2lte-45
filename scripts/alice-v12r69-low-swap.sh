#!/system/bin/sh
# One-shot, reversible low-swap repair for the supplied Samsung LMKD binary.
# Does not change swap size, compression ratio, kill scores, MGLRU or governor.
umask 077
S=/data/adb/alice
B=$S/low-swap.backup
L=$S/memory-experiment.lock
DAEMON=/system/bin/lmkd
EXPECTED=3bbca06f1f7dcc1be36b7e16d70e6ffe833fe420bab7a380b8582e3f3a822b49
BASE=ro.slmk.base_swaptotal
NOMINAL=ro.slmk.swap_free_low_percentage
SECOND=ro.slmk.2nd.swap_free_low_percentage
OVERRIDE=persist.device_config.lmkd_native.swap_free_low_percentage
EFFECTIVE=sys.lmk.slmk_16up_swap_free_low_percentage
ACTION=$1
pending=0
R=
KIND=
[ "$(id -u)" = 0 ] || { echo ALICE_ROOT_REQUIRED; exit 3; }
num() { case "$1" in ''|*[!0-9]*) return 1;; *) return 0;; esac; }
find_resetter() {
 R=$(command -v resetprop 2>/dev/null)
 if [ -n "$R" ]; then KIND=direct; return 0; fi
 for k in /data/adb/ksu/bin/ksud "$(command -v ksud 2>/dev/null)"; do
  [ -n "$k" ] && [ -x "$k" ] || continue
  # Verify the subcommand by reading a property, without changing it.
  timeout 3 "$k" resetprop ro.build.version.sdk >/dev/null 2>&1 || continue
  R=$k; KIND=ksud; return 0
 done
 return 1
}
resetter() {
 [ -n "$R" ] || find_resetter || return 1
 if [ "$KIND" = ksud ]; then "$R" resetprop -n "$1" "$2"
 else "$R" -n "$1" "$2"; fi
}
reinit() { timeout 8 "$DAEMON" --reinit; }
boot_id() { cat /proc/sys/kernel/random/boot_id; }
restore() {
 [ -d "$B" ] || return 0
 [ -f "$B/boot_id" ] && [ -f "$B/base" ] && [ -f "$B/nominal" ] && [ -f "$B/second" ] || return 1
 if [ "$(cat "$B/boot_id")" != "$(boot_id)" ]; then
  # Only RAM properties changed. A reboot already discarded this repair.
  rm -rf "$B"
  echo ALICE_LOW_SWAP_RESET_BY_REBOOT
  return 0
 fi
 old_base=$(cat "$B/base")
 old_nominal=$(cat "$B/nominal")
 old_second=$(cat "$B/second")
 [ -f "$B/applied_base" ] && [ -f "$B/applied_nominal" ] || return 1
 current_base=$(getprop "$BASE")
 current_nominal=$(getprop "$NOMINAL")
 current_second=$(getprop "$SECOND")
 [ "$current_base" = "$old_base" ] || [ "$current_base" = "$(cat "$B/applied_base")" ] || return 1
 [ "$current_nominal" = "$old_nominal" ] || [ "$current_nominal" = "$(cat "$B/applied_nominal")" ] || return 1
 [ "$current_second" = "$old_second" ] || [ "$current_second" = "$(cat "$B/applied_nominal")" ] || return 1
 resetter "$BASE" "$old_base" || return 1
 resetter "$NOMINAL" "$old_nominal" || return 1
 resetter "$SECOND" "$old_second" || return 1
 [ "$(getprop "$BASE")" = "$old_base" ] || return 1
 [ "$(getprop "$NOMINAL")" = "$old_nominal" ] || return 1
 [ "$(getprop "$SECOND")" = "$old_second" ] || return 1
 reinit || return 1
 rm -rf "$B"
 echo ALICE_LOW_SWAP_RESTORED
}
case "$ACTION" in
 status)
  echo "nominal=$(getprop "$NOMINAL") second=$(getprop "$SECOND") base_swap_mb=$(getprop "$BASE") effective=$(getprop "$EFFECTIVE") override=$(getprop "$OVERRIDE")"
  grep -E '^(MemAvailable|SwapTotal|SwapFree|MemFree|Inactive\(file\)):' /proc/meminfo
  exit 0;;
 apply|restore) ;;
 *) echo ALICE_UNKNOWN_ACTION; exit 2;;
esac
mkdir -p "$S" || exit 4
chmod 0700 "$S"
mkdir "$L" 2>/dev/null || { echo ALICE_LOW_SWAP_BUSY; exit 5; }
cleanup() {
 if [ "$pending" = 1 ]; then restore || echo ALICE_LOW_SWAP_RESTORE_FAILED; fi
 rmdir "$L" 2>/dev/null || :
}
trap cleanup 0
trap 'exit 143' 1 2 15
if [ "$ACTION" = restore ]; then
 restore || { echo ALICE_LOW_SWAP_RESTORE_FAILED; exit 6; }
 exit 0
fi
[ "$(getprop sys.boot_completed)" = 1 ] || exit 7
[ "$(getprop init.svc.lmkd)" = running ] || exit 7
actual=$(sha256sum "$DAEMON" 2>/dev/null | awk '{print $1}')
[ "$actual" = "$EXPECTED" ] || { echo ALICE_LMKD_BINARY_MISMATCH; exit 8; }
command -v timeout >/dev/null 2>&1 || exit 9
find_resetter || { echo ALICE_RESETPROP_UNAVAILABLE; exit 9; }
swap_kb=$(awk '$1=="SwapTotal:" {print $2}' /proc/meminfo)
available=$(awk '$1=="MemAvailable:" {print $2}' /proc/meminfo)
num "$swap_kb" && [ "$swap_kb" -ge 3000000 ] && [ "$swap_kb" -le 4200000 ] || exit 10
num "$available" && [ "$available" -ge 600000 ] || exit 10
# Scope to the single zRAM setup whose Samsung transform was analyzed.
awk 'NR>1 {n++; if ($1!="/dev/block/zram0") bad=1} END {exit !(n==1 && !bad)}' /proc/swaps || exit 10
nominal=10
override=$(getprop "$OVERRIDE")
if [ -n "$override" ]; then
 num "$override" && [ "$override" -ge 1 ] && [ "$override" -le 30 ] || {
  echo ALICE_EXISTING_OVERRIDE_REQUIRES_REVIEW; exit 11;
 }
 nominal=$override
fi
base_mb=$(((swap_kb+1023)/1024))
[ ! -d "$B" ] || { echo ALICE_LOW_SWAP_RESTORE_REQUIRED; exit 12; }
mkdir "$B" || exit 12
# Finish the backup before touching either property.
boot_id > "$B/boot_id" && getprop "$BASE" > "$B/base" &&
 getprop "$NOMINAL" > "$B/nominal" && getprop "$SECOND" > "$B/second" &&
 printf '%s\n' "$base_mb" > "$B/applied_base" &&
 printf '%s\n' "$nominal" > "$B/applied_nominal" || { rm -rf "$B"; exit 12; }
pending=1
if resetter "$BASE" "$base_mb" && resetter "$NOMINAL" "$nominal" && resetter "$SECOND" "$nominal" &&
   [ "$(getprop "$BASE")" = "$base_mb" ] &&
   [ "$(getprop "$NOMINAL")" = "$nominal" ] &&
   [ "$(getprop "$SECOND")" = "$nominal" ] && reinit; then
 n=0
 while [ "$n" -lt 5 ]; do
  if [ "$(getprop "$EFFECTIVE")" = "$nominal" ]; then
   echo "ALICE_LOW_SWAP_APPLIED nominal=$nominal effective=$nominal base_swap_mb=$base_mb"
   pending=0
   exit 0
  fi
  sleep 1
  n=$((n+1))
 done
fi
echo ALICE_LOW_SWAP_NOT_CONFIRMED
restore || { echo ALICE_LOW_SWAP_RESTORE_FAILED; exit 6; }
exit 13
