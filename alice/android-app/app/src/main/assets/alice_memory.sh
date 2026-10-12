#!/system/bin/sh
# ALICE V12R64 resource control. No direct LMKD kill, signal, GPU, or NPU.
# MGLRU and LMKD experimental trial are EXPLICIT, never automatic.
umask 077
K=/sys/kernel/alice
M=/sys/kernel/mm/lru_gen/enabled
P=persist.device_config.lmkd_native.thrashing_limit
LEGACY_P=$P
RP=ro.lmk.thrashing_limit
LOCK=/data/adb/alice/memory-experiment.lock
S=/data/adb/alice
ACTION=$1
[ "$(id -u)" = 0 ] || { echo ALICE_ROOT_REQUIRED >&2; exit 3; }

select_lmkd_property() {
 # Samsung One UI uses slmkd_native for thrashing, while AOSP uses lmkd_native.
 # Select only a property with an installed init trigger and reinit action.
 for f in /system/etc/init/lmkd.rc /vendor/etc/init/lmkd.rc \
          /product/etc/init/lmkd.rc /system_ext/etc/init/lmkd.rc; do
  [ -r "$f" ] || continue
  grep -F -q 'on property:lmkd.reinit=1' "$f" || continue
  for candidate in persist.device_config.slmkd_native.thrashing_limit \
                   persist.device_config.lmkd_native.thrashing_limit; do
   grep -F -q "on property:$candidate=" "$f" || continue
   P=$candidate
   case "$P" in
    persist.device_config.slmkd_native.*) RP=ro.slmk.thrashing_limit ;;
    *) RP=ro.lmk.thrashing_limit ;;
   esac
   return 0
  done
 done
 return 1
}
select_lmkd_property || :

num() {
 case "$1" in ""|*[!0-9]*) return 1;; *) return 0;; esac
}
booted() {
 [ "$(getprop sys.boot_completed 2>/dev/null)" = 1 ]
}
ensure_dir() {
 mkdir -p "$S" || return 1
 chmod 0700 "$S"
}
lock_trial() {
 ensure_dir || exit 20
 mkdir "$LOCK" 2>/dev/null || { echo ALICE_EXPERIMENT_RUNNING; exit 21; }
}
unlock_trial() { rmdir "$LOCK" 2>/dev/null || :; }
show() {
 echo "alice_version=$(cat "$K/version" 2>/dev/null || echo missing)"
 echo "alice_assessment=$(cat "$K/assessment" 2>/dev/null || echo unknown)"
 echo "alice_vm=$(cat "$K/vm_policy" 2>/dev/null || echo unknown)"
 echo "lru_gen=$(cat "$M" 2>/dev/null || echo missing)"
 echo "lmkd_service=$(getprop init.svc.lmkd 2>/dev/null)"
 echo "lmkd_thrashing_property=$P"
 echo "lmkd_thrashing_ro=$(getprop "$RP" 2>/dev/null)"
 echo "lmkd_thrashing_override=$(getprop "$P" 2>/dev/null)"
 echo "lmkd_reports_kills=$(getprop sys.lmk.reportkills 2>/dev/null)"
 echo "meminfo_begin"
 grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree|Cached|SReclaimable):' /proc/meminfo 2>/dev/null
 echo "meminfo_end"
 echo "psi_begin"
 cat /proc/pressure/memory 2>/dev/null || echo missing
 echo "psi_end"
 echo "reclaim=$(cat "$K/mm_reclaim" 2>/dev/null || echo unknown)"
}
has_lmkd_reinit() {
 [ "$(getprop init.svc.lmkd 2>/dev/null)" = running ] || return 1
 # AOSP has property triggers, but some Samsung ROMs do not. Prove from the
 # installed device's init rc, not from internet documentation.
 for f in /system/etc/init/lmkd.rc /vendor/etc/init/lmkd.rc \
          /product/etc/init/lmkd.rc /system_ext/etc/init/lmkd.rc; do
  [ -r "$f" ] || continue
  grep -F -q "on property:$P=" "$f" || continue
  grep -F -q 'on property:lmkd.reinit=1' "$f" || continue
  return 0
 done
 return 1
}
restore_lmkd() {
 if [ -f "$S/lmkd-trial.backup" ]; then
  # Interrupted trials must restore the original namespace, even after an
  # app/ROM update. Backups from V12R64 used the AOSP property only.
  restore_p=$LEGACY_P
  if [ -f "$S/lmkd-trial.property" ]; then
   restore_p=$(cat "$S/lmkd-trial.property")
  fi
  case "$restore_p" in
   persist.device_config.lmkd_native.thrashing_limit|persist.device_config.slmkd_native.thrashing_limit) ;;
   *) return 1 ;;
  esac
  original=$(cat "$S/lmkd-trial.backup" 2>/dev/null)
  setprop "$restore_p" "$original" || return 1
  [ "$(getprop "$restore_p" 2>/dev/null)" = "$original" ] || return 1
  rm -f "$S/lmkd-trial.backup" "$S/lmkd-trial.property"
 fi
}
restore_mglru() {
 if [ -f "$S/mglru-trial.backup" ]; then
  [ -w "$M" ] || return 1
  original=$(cat "$S/mglru-trial.backup")
  [ "$original" = 0 ] || return 1
  printf '0\n' > "$M" || return 1
  [ "$(cat "$M" 2>/dev/null)" = 0 ] || return 1
  rm -f "$S/mglru-trial.backup"
 fi
}
case "$ACTION" in
 status)
  show
  if has_lmkd_reinit; then echo "lmkd_runtime_config=supported_by_rc"
  else echo "lmkd_runtime_config=unsupported_or_unverified"; fi
  ;;
 mode)
  num "$2" && [ "$2" -le 5 ] || exit 2
  booted && [ -w "$K/mode" ] || exit 3
  printf '%s\n' "$2" > "$K/mode" || exit 4
  echo "ALICE_MODE=$(cat "$K/mode")"
  ;;
 policy-on|policy-off)
  booted && [ -w "$K/policy_enabled" ] || exit 3
  if [ "$ACTION" = policy-on ]; then value=1; else value=0; fi
  printf '%s\n' "$value" > "$K/policy_enabled" || exit 4
  echo "ALICE_POLICY=$(cat "$K/policy_enabled")"
  ;;
 mglru-trial)
  # USER CONFIRMATION REQUIRED. A full CPU/MM deadlock may prevent rollback.
  booted || exit 3
  [ -w "$M" ] || { echo ALICE_MGLRU_UNAVAILABLE; exit 4; }
  old=$(cat "$M" 2>/dev/null) || exit 4
  [ "$old" = 0 ] || { echo ALICE_MGLRU_ALREADY_ENABLED; exit 5; }
  av=$(awk '$1 == "MemAvailable:" {print $2}' /proc/meminfo)
  num "$av" && [ "$av" -ge 600000 ] || { echo ALICE_NOT_ENOUGH_AVAILABLE_RAM; exit 6; }
  lock_trial
  [ ! -f "$S/mglru-trial.backup" ] || { unlock_trial; echo ALICE_RESTORE_REQUIRED; exit 11; }
  echo 0 > "$S/mglru-trial.backup" || { unlock_trial; exit 12; }
  trap 'restore_mglru; unlock_trial' 0 1 2 15
  printf '1\n' > "$M" || exit 7
  echo "ALICE_MGLRU_TRIAL_ACTIVE=1"
  sleep 12
  restore_mglru || exit 10
  echo "ALICE_MGLRU_TRIAL_END=$(cat "$M" 2>/dev/null)"
  ;;
 lmkd-trial)
  # Temporary experiment only. Never alters lowmem_min_oom_score, foreground,
  # kill permission or lmkd service lifecycle. Restore original property.
  booted && has_lmkd_reinit || { echo ALICE_LMKD_DYNAMIC_UNSUPPORTED; exit 8; }
  num "$2" && [ "$2" -ge 35 ] && [ "$2" -le 100 ] || exit 2
  lock_trial
  [ ! -f "$S/lmkd-trial.backup" ] || { unlock_trial; echo ALICE_RESTORE_REQUIRED; exit 11; }
  original=$(getprop "$P" 2>/dev/null)
  printf '%s' "$P" > "$S/lmkd-trial.property" || { unlock_trial; exit 12; }
  printf '%s' "$original" > "$S/lmkd-trial.backup" || { unlock_trial; exit 12; }
  trap 'restore_lmkd; unlock_trial' 0 1 2 15
  setprop "$P" "$2" || exit 9
  [ "$(getprop "$P" 2>/dev/null)" = "$2" ] || { echo ALICE_LMKD_PROPERTY_NOT_APPLIED; exit 9; }
  echo "ALICE_LMKD_TRIAL_ACTIVE=$2"
  sleep 20
  restore_lmkd || exit 10
  echo "ALICE_LMKD_RESTORED=$(getprop "$P" 2>/dev/null)"
  ;;
 restore)
  # Called after an interrupted experiment or on user stop.
  restore_mglru || { echo ALICE_MGLRU_RESTORE_FAILED; exit 10; }
  restore_lmkd || { echo ALICE_LMKD_RESTORE_FAILED; exit 10; }
  echo ALICE_EXPERIMENTS_RESTORED
  ;;
 capability)
  echo "alice_kernel=$([ -f "$K/version" ] && echo yes || echo no)"
  echo "mglru=$([ -r "$M" ] && echo available || echo unavailable)"
  if has_lmkd_reinit; then echo "lmkd_dynamic=yes"; else echo "lmkd_dynamic=no"; fi
  ;;
 *)
  echo ALICE_UNKNOWN_ACTION >&2; exit 2 ;;
esac
