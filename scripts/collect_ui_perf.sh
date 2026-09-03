#!/system/bin/sh
# Read-only snapshots. No governor writes, cache drops, or gfxinfo resets.
# Run with: sh collect_ui_perf.sh com.android.systemui 20 > ui-perf.txt

package=${1:-com.android.systemui}
seconds=${2:-20}
case "$package" in
    ''|*[!a-zA-Z0-9_.]*) echo "Invalid Android package name" >&2; exit 2 ;;
esac
case "$seconds" in
    ''|*[!0-9]*) echo "Duration must be 5..30 seconds" >&2; exit 2 ;;
esac
if [ "${#seconds}" -gt 2 ]; then
    echo "Duration must be 5..30 seconds" >&2
    exit 2
fi
if [ "$seconds" -lt 5 ] || [ "$seconds" -gt 30 ]; then
    echo "Duration must be 5..30 seconds" >&2
    exit 2
fi
if ! command -v dumpsys >/dev/null 2>&1; then
    echo "Run this script on the Android device." >&2
    exit 2
fi

read_node() {
    [ -r "$1" ] || return 0
    printf '\n[%s]\n' "$1"
    cat "$1" 2>&1
}

snapshot() {
    seen_apps=
    printf '\n=== %s ===\n' "$1"
    date +%s
    for node in /proc/uptime /proc/stat /proc/meminfo /proc/vmstat \
        /proc/swaps /proc/sys/vm/swappiness \
        /proc/sys/kernel/sched_cpu_ui_hints \
        /sys/devices/system/cpu/online \
        /sys/class/power_supply/battery/status \
        /sys/class/power_supply/battery/temp; do
        read_node "$node"
    done
    for cpu in 0 4; do
        policy=/sys/devices/system/cpu/cpu$cpu/cpufreq
        for name in scaling_governor scaling_cur_freq scaling_min_freq \
            scaling_max_freq cpuinfo_min_freq cpuinfo_max_freq \
            schedutil/up_rate_limit_us schedutil/down_rate_limit_us \
            stats/time_in_state; do
            read_node "$policy/$name"
        done
    done
    for node in /dev/stune/schedtune.boost /dev/stune/schedtune.prefer_idle \
        /dev/stune/*/schedtune.boost \
        /dev/stune/*/schedtune.prefer_idle \
        /dev/cpuset/*/cpus \
        /dev/cpuctl/*/cpu.ui_hint_boost \
        /dev/cpuctl/*/cpu.ui_hint_prefer_idle \
        /sys/class/thermal/thermal_zone*/type \
        /sys/class/thermal/thermal_zone*/temp \
        /sys/block/zram*/mm_stat \
        /sys/class/devfreq/*/name \
        /sys/class/devfreq/*/governor \
        /sys/class/devfreq/*/cur_freq; do
        read_node "$node"
    done
    # Recents/animations may be drawn by the launcher instead of SystemUI.
    # Absent launcher packages are harmless and reported by dumpsys.
    for app in "$package" com.android.systemui com.sec.android.app.launcher \
        com.android.launcher3; do
        case " $seen_apps " in *" $app "*) continue ;; esac
        seen_apps="$seen_apps $app"
        for pid in $(pidof "$app" 2>/dev/null); do
            read_node "/proc/$pid/cgroup"
            for thread in /proc/"$pid"/task/*; do
                [ -r "$thread/comm" ] || continue
                case "$(cat "$thread/comm")" in
                    RenderThread) read_node "$thread/cgroup" ;;
                esac
            done
        done
        printf '\n[gfxinfo %s framestats]\n' "$app"
        dumpsys gfxinfo "$app" framestats 2>&1
    done
}

printf 'Read-only UI performance capture; package=%s duration=%ss\n' \
    "$package" "$seconds"
uname -r
printf '\n[cgroup mounts]\n'
awk '$3 == "cgroup" || $3 == "cgroup2" { print }' /proc/mounts
for prop in ro.product.device ro.build.version.release ro.build.version.sdk \
    ro.build.display.id; do
    printf '%s=' "$prop"
    getprop "$prop"
done
snapshot before
echo "Now repeat the stuttering gesture for $seconds seconds." >&2
sleep "$seconds"
snapshot after
echo "Capture finished. No performance settings were changed." >&2
