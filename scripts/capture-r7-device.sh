#!/system/bin/sh
# Read-only, bounded sampling. Output is streamed to the adb host.
read_node() {
    [ -r "$1" ] || return 0
    printf '\n[%s]\n' "$1"
    cat "$1" 2>&1
}
printf 'ALICE UI/reclaim/thermal capture\n'
uname -a
for node in /proc/swaps /proc/sys/vm/swappiness /proc/mounts \
    /proc/sys/kernel/sched_cpu_ui_hints; do read_node "$node"; done
for node in /dev/stune/*/schedtune.boost /dev/stune/schedtune.boost \
    /sys/class/thermal/thermal_zone*/type; do read_node "$node"; done
for cpu in 0 4; do
    read_node "/sys/devices/system/cpu/cpu$cpu/cpufreq/stats/time_in_state"
done
count=0
while [ "$count" -lt 25 ]; do
    printf '\n=== sample %s ===\n' "$count"
    for node in /proc/uptime /proc/stat /proc/meminfo /proc/vmstat \
        /proc/pressure/memory /proc/pressure/cpu /proc/pressure/io \
        /sys/kernel/mm/lru_gen/enabled /sys/kernel/mm/lru_gen/diag \
        /sys/kernel/mm/lru_gen/stats /sys/kernel/alice/mm_reclaim \
        /sys/devices/system/cpu/online /sys/class/power_supply/battery/temp \
        /sys/class/thermal/thermal_zone*/temp /sys/block/zram0/mm_stat; do
        read_node "$node"
    done
    for cpu in 0 4; do
        policy=/sys/devices/system/cpu/cpu$cpu/cpufreq
        for name in scaling_governor scaling_cur_freq scaling_min_freq scaling_max_freq \
            energy_step/up_rate_limit_us energy_step/down_rate_limit_us; do
            read_node "$policy/$name"
        done
    done
    for app in com.android.systemui com.sec.android.app.launcher com.android.launcher3; do
        for pid in $(pidof "$app" 2>/dev/null); do
            printf '\n[process %s pid=%s]\n' "$app" "$pid"
            for name in stat status wchan stack cgroup; do read_node "/proc/$pid/$name"; done
        done
    done
    count=$((count + 1))
    sleep 2
done
for cpu in 0 4; do
    read_node "/sys/devices/system/cpu/cpu$cpu/cpufreq/stats/time_in_state"
done
