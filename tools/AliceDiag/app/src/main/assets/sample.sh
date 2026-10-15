# Fast read-only sample. File reads use shell builtins: no cat/awk subprocess per node.
PATH=/system/bin:/system/xbin:/vendor/bin:/sbin
export PATH LC_ALL=C
read_node() {
    [ -r "$1" ] || return 0
    printf '\n@@ %s\n' "$1"
    while IFS= read -r line || [ -n "$line" ]; do printf '%s\n' "$line"; done < "$1"
    return 0
}
read_node /proc/uptime
printf '\n@@ /proc/stat\n'
while IFS= read -r line; do
    case "$line" in cpu*|ctxt\ *|processes\ *|procs_running\ *|procs_blocked\ *) printf '%s\n' "$line";; esac
done < /proc/stat
printf '\n@@ /proc/meminfo\n'
while IFS= read -r line; do
    case "$line" in MemTotal:*|MemFree:*|MemAvailable:*|Cached:*|SwapCached:*|SwapTotal:*|SwapFree:*|Active*|Inactive*|Dirty:*|Writeback:*|Slab:*|PageTables:*) printf '%s\n' "$line";; esac
done < /proc/meminfo
printf '\n@@ /proc/vmstat (selected cumulative counters; absence is retained)\n'
while IFS= read -r line; do
    case "$line" in pswpin\ *|pswpout\ *|pgmajfault\ *|pgscan*|pgsteal*|allocstall*|compact_stall\ *|compact_fail\ *|compact_success\ *|oom_kill\ *|workingset_refault*) printf '%s\n' "$line";; esac
done < /proc/vmstat
for n in cpu memory io; do read_node /proc/pressure/$n; done
for d in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$d" ] || continue
    for n in scaling_cur_freq scaling_min_freq scaling_max_freq scaling_governor; do read_node "$d/$n"; done
    [ "$detail" != 1 ] || read_node "$d/stats/time_in_state"
done
read_node /sys/devices/system/cpu/online
for d in /sys/class/thermal/thermal_zone*; do
    [ -d "$d" ] || continue
    read_node "$d/type"
    read_node "$d/temp"
done
for d in /sys/devices/platform/18500000.mali /sys/devices/platform/14ac0000.mali /sys/class/misc/mali0/device; do
    [ -d "$d" ] || continue
    for n in clock utilization; do read_node "$d/$n"; done
    if [ "$detail" = 1 ]; then
        for n in dvfs_governor dvfs_max_lock dvfs_min_lock time_in_state; do read_node "$d/$n"; done
    fi
    break
done
read_node /sys/kernel/mm/lru_gen/enabled
read_node /sys/power/alice_power_hint
for n in gpu_clock gpu_busy gpu_boost gpu_dvfs_load; do read_node /sys/kernel/gpu/$n; done
for d in /sys/block/zram*; do read_node "$d/mm_stat"; done
if [ "$detail" = 1 ]; then
    printf '\n@@ process cumulative CPU time (not instantaneous CPU percent)\n'
    ps -A -o PID,UID,TIME,RSS,NAME 2>/dev/null
    printf '\n@@ kernel wakeup counters (cumulative)\n'
    if [ -r /sys/kernel/debug/wakeup_sources ]; then
        read_node /sys/kernel/debug/wakeup_sources
    elif [ -r /proc/wakelocks ]; then
        read_node /proc/wakelocks
    fi
    for n in status capacity temp voltage_now current_now current_avg charge_counter charge_full charge_full_design cycle_count health; do
        read_node /sys/class/power_supply/battery/$n
    done
fi
exit 0
