#!/system/bin/sh
# Read-only two snapshots. Run via 'adb shell sh /data/local/tmp/... [game.package]'
game="${1:-}"
probe() {
 echo "== timestamp =="; date
 echo "== device =="; getprop ro.product.device; uname -r
 echo "== cpu governors/frequency =="
 for p in /sys/devices/system/cpu/cpufreq/policy*; do
   [ -r "$p/scaling_governor" ] || continue
   echo "$p cpus=$(cat "$p/related_cpus" 2>/dev/null) gov=$(cat "$p/scaling_governor" 2>/dev/null) cur=$(cat "$p/scaling_cur_freq" 2>/dev/null) max=$(cat "$p/scaling_max_freq" 2>/dev/null)"
 done
 echo "== thermal (raw values) =="
 for t in /sys/class/thermal/thermal_zone*; do
   [ -r "$t/type" ] && [ -r "$t/temp" ] && echo "$(cat "$t/type"): $(cat "$t/temp")"
 done
 echo "== zram =="; cat /sys/block/zram0/comp_algorithm 2>/dev/null
 cat /sys/block/zram0/mm_stat 2>/dev/null
 echo "== memory PSI =="; cat /proc/pressure/memory 2>/dev/null
 echo "== LMKD =="; getprop init.svc.lmkd; getprop ro.lmk.use_psi
 echo "== key memory metrics =="; grep -E 'MemAvailable|SwapFree|SwapTotal|Cached' /proc/meminfo 2>/dev/null
 echo "== GPU devfreq available ==";
 for d in /sys/class/devfreq/*; do case "$d" in *gpu*|*mali*|*g3d*) echo "$d: $(cat "$d/cur_freq" 2>/dev/null) max=$(cat "$d/max_freq" 2>/dev/null)";; esac; done
 [ -n "$game" ] && dumpsys gfxinfo "$game" 2>/dev/null | grep -E 'Total frames rendered|Janky frames|90th percentile|95th percentile|99th percentile' | head -n 8
}
probe
sleep 15
probe
echo "=== End: no sysfs values modified ==="
