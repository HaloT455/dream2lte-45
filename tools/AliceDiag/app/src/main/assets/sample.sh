# Read-only telemetry. No sysfs/proc writes, root daemons or background jobs.
PATH=/system/bin:/system/xbin:/vendor/bin:/sbin
export PATH LC_ALL=C
read_node() {
    [ -r "$1" ] || return 0
    printf '\n@@ %s\n' "$1"
    cat "$1" 2>/dev/null
    return 0
}
read_node /proc/uptime
printf '\n@@ /proc/stat\n'
awk '/^cpu|^ctxt |^processes |^procs_running |^procs_blocked / {print}' /proc/stat
read_node /proc/meminfo
printf '\n@@ /proc/vmstat (selected cumulative counters)\n'
awk '/^(pswpin|pswpout|pgmajfault|pgscan|pgsteal|allocstall|compact_stall|compact_fail|compact_success|oom_kill|workingset_refault)/ {print}' /proc/vmstat
for n in cpu memory io; do read_node /proc/pressure/$n; done
for d in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$d" ] || continue
    for n in scaling_cur_freq scaling_min_freq scaling_max_freq scaling_governor stats/time_in_state; do read_node "$d/$n"; done
done
for n in present online; do read_node /sys/devices/system/cpu/$n; done
for d in /sys/class/thermal/thermal_zone*; do
    [ -d "$d" ] || continue
    read_node "$d/type"
    read_node "$d/temp"
done
for d in /sys/class/power_supply/battery; do
    for n in status capacity temp voltage_now current_now current_avg charge_counter charge_full charge_full_design cycle_count health; do
        read_node "$d/$n"
    done
done
for d in /sys/devices/platform/18500000.mali /sys/devices/platform/14ac0000.mali /sys/class/misc/mali0/device; do
    [ -d "$d" ] || continue
    for n in clock utilization dvfs_governor dvfs_max_lock dvfs_min_lock time_in_state load_boost; do read_node "$d/$n"; done
    break
done
for n in enabled min_ttl_ms; do read_node /sys/kernel/mm/lru_gen/$n; done
read_node /sys/power/alice_power_hint
for n in gpu_clock gpu_busy gpu_governor gpu_boost gpu_dvfs_load gpu_temp; do read_node /sys/kernel/gpu/$n; done
for d in /sys/block/zram*; do
    for n in mm_stat io_stat disksize; do read_node "$d/$n"; done
done
if [ "$detail" = 1 ]; then
    printf '\n@@ process cumulative CPU time (not instantaneous CPU percent)\n'
    ps -A -o PID,UID,TIME,RSS,NAME 2>/dev/null
    printf '\n@@ kernel wakeup counters (cumulative)\n'
    if [ -r /sys/kernel/debug/wakeup_sources ]; then
        head -c 65536 /sys/kernel/debug/wakeup_sources
    elif [ -r /proc/wakelocks ]; then
        head -c 65536 /proc/wakelocks
    fi
    printf '\n@@ power state\n'
    dumpsys -t 2 power 2>/dev/null | awk '/^[[:space:]]*m(Wakefulness|IsPowered|PlugType|StayOn|WakeLockSummary)=/ {print}'
fi
if [ "$frames" = 1 ]; then
    # Keep only a package name, never activity arguments, notifications or UI text.
    pkg=$(dumpsys -t 2 activity activities 2>/dev/null | awk '
        /mResumedActivity:|topResumedActivity=/ {
            for(i=1;i<=NF;i++) if($i ~ /^[A-Za-z0-9_.]+\/[A-Za-z0-9_.$]+/) {
                split($i,a,"/"); print a[1]; exit
            }
        }')
    printf '\n@@ foreground package (sampled, not full usage history)\n%s\n' "$pkg"
    for target in com.android.systemui "$pkg"; do
        [ -n "$target" ] || continue
        case "$target" in *[!A-Za-z0-9_.]*) continue ;; esac
        printf '\n@@ gfxinfo summary %s (cumulative, no reset)\n' "$target"
        dumpsys -t 2 gfxinfo "$target" 2>/dev/null | awk '
            /^[[:space:]]*(Stats since|Total frames|Janky frames|50th percentile|90th percentile|95th percentile|99th percentile|Number |HISTOGRAM:|GPU HISTOGRAM:|Pipeline=)/ {print}'
    done
fi
exit 0
