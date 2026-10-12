#!/system/bin/sh
# ALICE V12R69 non-destructive One UI / MGLRU / LMKD snapshot.
# Never changes LMKD parameters, CPU governor, or thermal policy.
OUT="${1:-/data/local/tmp/alice_v12r69}"
mkdir -p "$OUT" || exit 1
NOW="$(date +%Y%m%d_%H%M%S)"
P="$OUT/$NOW"
mkdir -p "$P" || exit 1
{
  date
  uname -a
  getprop ro.boot.bootreason
  getprop sys.boot.reason
  getprop ro.product.model
  echo '=== MGLRU ==='
  for f in /sys/kernel/mm/lru_gen/enabled /sys/kernel/mm/lru_gen/lru_gen_boot_compat /sys/kernel/mm/lru_gen/min_ttl_ms /sys/kernel/mm/lru_gen/diag; do
    if [ -r "$f" ]; then echo "$f"; cat "$f"; fi
  done
  echo '=== PSI ==='
  cat /proc/pressure/memory 2>/dev/null
  echo '=== MEMINFO ==='
  cat /proc/meminfo
  echo '=== VMSTAT ==='
  cat /proc/vmstat
  echo '=== SWAP ==='
  cat /proc/swaps
  cat /sys/block/zram0/mm_stat 2>/dev/null
  echo '=== UI PIDS ==='
  pidof com.sec.android.app.launcher
  pidof com.android.systemui
  echo '=== GOVERNORS ==='
  for p in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -r "$p/scaling_governor" ] || continue
    echo "$p"; cat "$p/scaling_governor"; cat "$p/scaling_cur_freq"
  done
  echo '=== DEVICE_CONFIG ==='
  device_config get lmkd_native swap_free_low_percentage 2>&1
  device_config get lmkd_native thrashing_limit 2>&1
} > "$P/state.txt" 2>&1
logcat -b events -d -v threadtime > "$P/events.txt" 2>&1
logcat -b main -b system -b crash -d -v threadtime > "$P/android.txt" 2>&1
dmesg > "$P/dmesg.txt" 2>&1
echo "$P"
