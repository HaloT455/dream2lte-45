#!/system/bin/sh
# R5: user-requested LRU control and snapshots only. No resident polling loop.
set -u
M=/sys/kernel/mm/lru_gen/enabled
action=${1:-status}
case "$action" in status|on|off|trial) ;; *) echo ALICE_BAD_ACTION; exit 2;; esac
[ "$(id -u)" = 0 ] || { echo ALICE_ROOT_REQUIRED; exit 3; }

snapshot() {
 echo "=== ALICE LRU R5: $(date '+%Y-%m-%d %H:%M:%S') ==="
 echo "kernel=$(cat /proc/sys/kernel/osrelease 2>/dev/null)"
 echo "mglru=$(cat "$M" 2>/dev/null || echo unavailable)"
 for file in /sys/kernel/mm/lru_gen/features /sys/kernel/mm/lru_gen/stats /sys/kernel/alice/mm_reclaim; do
  [ ! -r "$file" ] || { echo "$file"; cat "$file"; }
 done
 echo '=== RAM / PSI ==='
 awk '/^(MemTotal|MemAvailable|SwapTotal|SwapFree):/' /proc/meminfo
 cat /proc/pressure/memory 2>/dev/null || :
 echo '=== CPU ==='
 for policy in /sys/devices/system/cpu/cpufreq/policy*; do
  [ -d "$policy" ] || continue
  echo "$policy"
  for name in scaling_governor scaling_cur_freq scaling_min_freq scaling_max_freq; do
   echo "$name=$(cat "$policy/$name" 2>/dev/null)"
  done
 done
 echo '=== TEMPERATURE ==='
 for zone in /sys/class/thermal/thermal_zone*; do
  [ -r "$zone/type" ] && [ -r "$zone/temp" ] || continue
  echo "$(cat "$zone/type")=$(cat "$zone/temp")"
 done
 echo "battery_temp=$(cat /sys/class/power_supply/battery/temp 2>/dev/null)"
 echo '=== CPU LOAD ==='
 dumpsys cpuinfo 2>/dev/null || :
}

cool_enough() {
 found=0
 for zone in /sys/class/thermal/thermal_zone*; do
  [ -r "$zone/type" ] && [ -r "$zone/temp" ] || continue
  type=$(tr '[:upper:]' '[:lower:]' < "$zone/type")
  case "$type" in *cpu*|*mngs*|*apollo*|*gpu*|*soc*|*exynos*|*mali*)
   raw=$(cat "$zone/temp")
   case "$raw" in ''|*[!0-9]*) continue;; esac
   if [ "$raw" -ge 1000 ]; then c=$((raw/1000))
   elif [ "$raw" -gt 200 ]; then c=$((raw/10))
   else c=$raw; fi
   found=1
   [ "$c" -lt 53 ] || { echo "ALICE_SOC_HOT_$c"; return 1; }
   ;; esac
 done
 [ "$found" = 1 ] || { echo ALICE_THERMAL_UNAVAILABLE; return 1; }
 bat=$(cat /sys/class/power_supply/battery/temp 2>/dev/null || :)
 case "$bat" in ''|*[!0-9]*) echo ALICE_BATTERY_UNAVAILABLE; return 1;; esac
 [ "$bat" -lt 390 ] || { echo ALICE_BATTERY_HOT; return 1; }
}

set_lru() {
 [ -w "$M" ] || { echo ALICE_MGLRU_UNAVAILABLE; return 1; }
 printf '%s\n' "$1" > "$M" || return 1
 [ "$(cat "$M" 2>/dev/null)" = "$1" ] || {
  echo ALICE_MGLRU_STATE_MISMATCH; return 1;
 }
 echo "ALICE_MGLRU=$1"
}

case "$action" in
 status) snapshot ;;
 off) set_lru 0 || exit 4; snapshot ;;
 on|trial)
  [ "$(getprop sys.boot_completed 2>/dev/null)" = 1 ] || {
   echo ALICE_BOOT_NOT_COMPLETED; exit 5;
  }
  cool_enough || { snapshot; exit 6; }
  if [ "$action" = trial ]; then
   [ "$(cat "$M" 2>/dev/null)" = 0 ] || {
    echo ALICE_TRIAL_REQUIRES_OFF; exit 7;
   }
   # Userspace cleanup cannot recover a deadlocked kernel.
   trap 'set_lru 0' 0
   trap 'exit 8' 1 2 15
  fi
  set_lru 1 || exit 4
  if [ "$action" = trial ]; then
   sleep 8
   set_lru 0 || exit 4
   trap - 0 1 2 15
   echo ALICE_TRIAL_FINISHED_OFF
  fi
  snapshot
  ;;
esac
