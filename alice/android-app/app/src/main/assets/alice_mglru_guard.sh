#!/system/bin/sh
# ALICE V12R65 guarded MGLRU supervisor for Exynos8895
# No LMKD kill, no CPU/GPU/DVFS, no thermal or watchdog override.
set -u
umask 077
STATE=/data/adb/alice/mglru-v12r65
LOCK=$STATE/active
PAUSE=$STATE/paused
M=/sys/kernel/mm/lru_gen/enabled
R=/sys/kernel/alice/mm_reclaim
ACTION=$1
[ "$(id -u)" = 0 ] || { echo ALICE_ROOT_REQUIRED; exit 3; }
isnum() { case "$1" in ''|*[!0-9]*) return 1;; esac; return 0; }
token() {
 cat /proc/sys/kernel/random/boot_id 2>/dev/null ||
  awk '$1=="btime" {print $2;exit}' /proc/stat
}
init() { mkdir -p "$STATE" && chmod 0700 "$STATE"; }
cleanup_stale() {
 [ -d "$LOCK" ] || return 0
 old=$(cat "$LOCK/boot" 2>/dev/null || :)
 current=$(token)
 if [ -n "$current" ] && [ -n "$old" ] && [ "$current" != "$old" ]; then
  rm -f "$LOCK/boot"
  rmdir "$LOCK" 2>/dev/null || :
 fi
}
acquire() {
 init || return 1
 cleanup_stale
 mkdir "$LOCK" 2>/dev/null || { echo ALICE_MGLRU_BUSY; return 1; }
 token > "$LOCK/boot"
}
release() { rm -f "$LOCK/boot"; rmdir "$LOCK" 2>/dev/null || :; }
restore() {
 [ -w "$M" ] || { echo ALICE_MGLRU_RESTORE_UNAVAILABLE; return 1; }
 value=$(cat "$M" 2>/dev/null || :)
 if [ "$value" != 0 ]; then printf '0\n' > "$M" || return 1; fi
 [ "$(cat "$M" 2>/dev/null)" = 0 ] || return 1
 rm -f "$STATE/enabled-by-alice"
 echo ALICE_MGLRU_OFF
}
pressure() {
 total=$(awk '$1=="MemTotal:" {print $2}' /proc/meminfo)
 avail=$(awk '$1=="MemAvailable:" {print $2}' /proc/meminfo)
 isnum "$total" && isnum "$avail" && [ "$total" -gt 0 ] || {
  echo ALICE_GATE_NO_MEMINFO; return 1;
 }
 [ "$avail" -ge 320000 ] || { echo ALICE_GATE_RAM_TOO_LOW; return 1; }
 [ $((avail * 100 / total)) -le 13 ] || {
  echo ALICE_GATE_NO_RAM_PRESSURE; return 1;
 }
 [ -r /proc/pressure/memory ] || { echo ALICE_GATE_PSI_MISSING; return 1; }
 awk '
 /^some / {for(i=1;i<=NF;i++) if($i~/^avg10=/){split($i,a,"=");s=a[2]+0;fs=1}}
 /^full / {for(i=1;i<=NF;i++) if($i~/^avg10=/){split($i,a,"=");f=a[2]+0;ff=1}}
 END {exit !(fs&&ff&&s>=5&&s<22&&f<2)}
 ' /proc/pressure/memory || { echo ALICE_GATE_PSI_NOT_ELIGIBLE; return 1; }
}
temperature() {
 found=0
 for zone in /sys/class/thermal/thermal_zone*; do
  [ -r "$zone/type" ] && [ -r "$zone/temp" ] || continue
  type=$(tr '[:upper:]' '[:lower:]' < "$zone/type" 2>/dev/null)
  case "$type" in
   *cpu*|*mngs*|*apollo*|*gpu*|*soc*|*exynos*|*mali*)
    raw=$(cat "$zone/temp" 2>/dev/null)
    isnum "$raw" || continue
    if [ "$raw" -ge 1000 ]; then c=$((raw/1000))
    elif [ "$raw" -gt 200 ]; then c=$((raw/10))
    else c=$raw; fi
    found=1
    [ "$c" -lt 53 ] || { echo "ALICE_GATE_SOC_HOT_$c"; return 1; }
    ;;
  esac
 done
 [ "$found" = 1 ] || { echo ALICE_GATE_NO_SOC_THERMAL; return 1; }
 [ -r /sys/class/power_supply/battery/temp ] || {
  echo ALICE_GATE_NO_BAT_THERMAL; return 1;
 }
 bat=$(cat /sys/class/power_supply/battery/temp)
 isnum "$bat" || return 1
 [ "$bat" -lt 390 ] || { echo ALICE_GATE_BATTERY_HOT; return 1; }
}
reclaim_count() {
 filedata=$(cat "$R" 2>/dev/null || :)
 echo "$filedata" | tr ' ' '\n' | awk -F= -v key="$1" '$1==key {print $2;exit}'
}
case "$ACTION" in
 status)
  echo "mglru=$(cat "$M" 2>/dev/null || echo unavailable)"
  if [ -f "$PAUSE" ]; then echo "guard=PAUSED_$(cat "$PAUSE")"
  else echo guard=READY; fi
  echo "reclaim=$(cat "$R" 2>/dev/null || echo unavailable)"
  ;;
 probe)
  [ "$(getprop sys.boot_completed 2>/dev/null)" = 1 ] || exit 4
  [ -w "$M" ] && [ "$(cat "$M" 2>/dev/null)" = 0 ] || {
   echo ALICE_GATE_MGLRU_NOT_OFF; exit 5;
  }
  temperature || exit 6
  pressure || exit 7
  [ ! -f "$PAUSE" ] || { echo ALICE_GATE_PAUSED; exit 8; }
  echo ALICE_MGLRU_ELIGIBLE
  ;;
 manual|auto)
  [ "$(getprop sys.boot_completed 2>/dev/null)" = 1 ] || exit 4
  [ -w "$M" ] && [ "$(cat "$M" 2>/dev/null)" = 0 ] || {
   echo ALICE_GATE_MGLRU_NOT_OFF; exit 5;
  }
  [ ! -f "$PAUSE" ] || { echo ALICE_GATE_PAUSED; exit 8; }
  temperature || exit 6
  if [ "$ACTION" = auto ]; then pressure || exit 7; fi
  acquire || exit 9
  before_stall=$(reclaim_count no_progress)
  before_backoff=$(reclaim_count backoffs)
  [ -n "$before_stall" ] && [ -n "$before_backoff" ] || {
   release; echo ALICE_GATE_NO_RECLAIM_STATS; exit 10;
  }
  touch "$STATE/enabled-by-alice"
  # Kernel deadlock cannot be recovered by userspace trap.
  trap 'restore; release' 0 1 2 15
  printf '1\n' > "$M" || exit 11
  [ "$(cat "$M" 2>/dev/null)" = 1 ] || exit 12
  echo ALICE_MGLRU_ON_TRIAL_8S
  sleep 8
  restore || { echo ALICE_MGLRU_RESTORE_FAILED; exit 13; }
  after_stall=$(reclaim_count no_progress)
  after_backoff=$(reclaim_count backoffs)
  if isnum "$before_stall" && isnum "$after_stall" &&
     isnum "$before_backoff" && isnum "$after_backoff"; then
   ds=$((after_stall-before_stall))
   db=$((after_backoff-before_backoff))
  else ds=-1; db=-1; fi
  echo "ALICE_NO_PROGRESS_DELTA=$ds"
  echo "ALICE_BACKOFF_DELTA=$db"
  if [ "$ds" -ne 0 ] || [ "$db" -ne 0 ]; then
   echo reclaim_stalls > "$PAUSE"
   echo ALICE_MGLRU_AUTO_PAUSED_AFTER_STALL
  elif ! temperature; then
   echo thermal_limit > "$PAUSE"
   echo ALICE_MGLRU_AUTO_PAUSED_AFTER_HEAT
  fi
  echo ALICE_MGLRU_FINISHED_OFF
  ;;
 restore)
  init || exit 2
  restore
  cleanup_stale
  ;;
 *) echo ALICE_BAD_ACTION; exit 2;;
esac
