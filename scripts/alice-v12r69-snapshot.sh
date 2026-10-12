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
  device_config get slmkd_native thrashing_limit 2>&1
  echo '=== LMKD PROPERTIES ==='
  for prop in ro.lmk.swap_free_low_percentage ro.slmk.swap_free_low_percentage \
      ro.slmk.2nd.swap_free_low_percentage \
      persist.device_config.lmkd_native.swap_free_low_percentage \
      sys.lmk.slmk_16up_swap_free_low_percentage \
      sys.lmk.slmk_16up_swap_used_threshold_kb \
      persist.sys.zram.ram_expand_size \
      ro.lmk.thrashing_limit ro.slmk.thrashing_limit \
      persist.device_config.lmkd_native.thrashing_limit \
      persist.device_config.slmkd_native.thrashing_limit; do
    echo "$prop=$(getprop "$prop")"
  done
  echo '=== ROM POLICY ==='
  for f in /system/etc/init/lmkd.rc /vendor/etc/init/lmkd.rc \
      /system_ext/etc/init/lmkd.rc /product/etc/init/lmkd.rc \
      /system/bin/init.mglru.sh; do
    [ -r "$f" ] || continue
    echo "$f"; cat "$f"
  done
  for f in /system/bin/lmkd /vendor/bin/lmkd; do
    [ -r "$f" ] && sha256sum "$f"
  done
} > "$P/state.txt" 2>&1
logcat -b events -d -v threadtime > "$P/events.txt" 2>&1
logcat -b main -b system -b crash -d -v threadtime > "$P/android.txt" 2>&1
dmesg > "$P/dmesg.txt" 2>&1
echo "$P"
