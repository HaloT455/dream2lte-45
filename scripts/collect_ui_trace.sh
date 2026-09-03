#!/system/bin/sh
# UI1-Trace: a bounded, on-demand trace. No performance or SELinux changes.
# stdout is a text bundle; stderr reports progress/errors. No log file on UFS.
set -eu

seconds=${1-15}
case "$seconds" in
    ''|*[!0-9]*) echo 'Duration must be 5..20 seconds.' >&2; exit 2 ;;
esac
if [ "${#seconds}" -gt 2 ] || [ "$seconds" -lt 5 ] || [ "$seconds" -gt 20 ]; then
    echo 'Duration must be 5..20 seconds.' >&2
    exit 2
fi
[ "$(id -u)" = 0 ] || { echo 'Run through su.' >&2; exit 2; }
command -v atrace >/dev/null || { echo 'atrace is missing.' >&2; exit 2; }

trace_dir=
mounted_here=0
trace_owned=0
cleanup() {
    result=$?
    trap - EXIT HUP INT TERM PIPE
    if [ "$trace_owned" = 1 ]; then
        if ! atrace --async_stop >/dev/null; then
            echo 'Trace cleanup failed. Reboot before normal use.' >&2
            result=1
        fi
        if ! printf '0\n' > "$trace_dir/tracing_on"; then
            echo 'Could not stop tracing. Reboot before normal use.' >&2
            result=1
        fi
    fi
    if [ "$mounted_here" = 1 ]; then
        if ! umount "$trace_dir"; then
            echo 'Temporary tracefs mount remains until reboot.' >&2
            result=1
        fi
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM PIPE

for candidate in /sys/kernel/tracing /sys/kernel/debug/tracing; do
    if [ -e "$candidate/trace_marker" ]; then
        trace_dir=$candidate
        break
    fi
done
if [ -z "$trace_dir" ]; then
    if ! awk '$NF == "tracefs" { found=1 } END { exit !found }' /proc/filesystems; then
        echo 'Kernel has no tracefs. Check that UI1-Trace is installed.' >&2
        exit 1
    fi
    trace_dir=/sys/kernel/tracing
    [ -d "$trace_dir" ] || { echo 'Kernel tracefs mount point is missing.' >&2; exit 1; }
    if awk -v p="$trace_dir" '$2 == p { found=1 } END { exit !found }' /proc/mounts; then
        echo 'Tracing path is mounted but unusable. Stop; do not change SELinux.' >&2
        exit 1
    fi
    # Standard tracefs mount only; never chmod, remount system, or change policy.
    mount -t tracefs -o nosuid,nodev,noexec tracefs "$trace_dir" || {
        echo 'Cannot mount tracefs. Send this error; do not change SELinux.' >&2
        exit 1
    }
    mounted_here=1
fi
for node in tracing_on trace trace_marker events/enable; do
    [ -w "$trace_dir/$node" ] || {
        echo "Trace permission unavailable: $node. Stop; do not change SELinux." >&2
        exit 1
    }
done
[ "$(cat "$trace_dir/current_tracer")" = nop ] || {
    echo 'Another tracer is selected. Save/stop it first.' >&2; exit 1;
}
[ "$(cat "$trace_dir/events/enable")" = 0 ] || {
    echo 'Trace events are already enabled. Save/stop that session first.' >&2; exit 1;
}
for prop in debug.atrace.tags.enableflags debug.atrace.app_number debug.atrace.user_initiated; do
    case "$(getprop "$prop")" in
        ''|0|0x0|false) ;;
        *) echo "Another trace session is active ($prop). Stop it first." >&2; exit 1 ;;
    esac
done

available=$(atrace --list_categories)
has_category() {
    printf '%s\n' "$available" | awk -v c="$1" '$1 == c { yes=1 } END { exit !yes }'
}
set --
for category in sched freq idle gfx view wm am binder_driver; do
    has_category "$category" || { echo "Missing trace category: $category" >&2; exit 1; }
    set -- "$@" "$category"
done
for category in memreclaim disk; do
    if has_category "$category"; then set -- "$@" "$category"; fi
done

read_node() {
    [ -r "$1" ] || return 0
    printf '\n[%s]\n' "$1"
    cat "$1"
}
snapshot() {
    printf '\n=== %s ===\n' "$1"
    for node in /proc/uptime /proc/stat /proc/meminfo /proc/vmstat /proc/swaps \
        /proc/sys/kernel/sched_cpu_ui_hints /proc/sys/kernel/sched_sync_hint_enable \
        /sys/class/power_supply/battery/status /sys/class/power_supply/battery/temp \
        /sys/class/thermal/thermal_zone*/type /sys/class/thermal/thermal_zone*/temp \
        /dev/cpuctl/*/cpu.ui_hint_boost /dev/cpuctl/*/cpu.ui_hint_prefer_idle; do
        read_node "$node"
    done
    for cpu in 0 4; do
        for name in scaling_cur_freq scaling_max_freq stats/time_in_state; do
            read_node "/sys/devices/system/cpu/cpu$cpu/cpufreq/$name"
        done
    done
    for app in com.sec.android.app.launcher com.android.systemui; do
        for pid in $(pidof "$app" 2>/dev/null || true); do
            read_node "/proc/$pid/cgroup"
            for task in /proc/"$pid"/task/*; do
                [ -r "$task/comm" ] || continue
                case "$(cat "$task/comm")" in
                    RenderThread) read_node "$task/cgroup" ;;
                esac
            done
        done
        printf '\n[gfxinfo %s]\n' "$app"
        dumpsys gfxinfo "$app" framestats || true
    done
}

printf 'UI1-Trace capture v1; duration=%ss; buffer=4096 KiB per CPU\n' "$seconds"
uname -r
getenforce
printf 'Trace directory: %s\nCategories: %s\n' "$trace_dir" "$*"
snapshot before
trace_owned=1
atrace --async_start -b 4096 "$@" >/dev/null
# Some Android atrace versions return success even when setup fails.
[ "$(cat "$trace_dir/tracing_on")" = 1 ] || { echo 'Trace did not start.' >&2; exit 1; }
for event in sched/sched_switch sched/sched_wakeup power/cpu_frequency \
    power/cpu_idle binder/binder_transaction binder/binder_transaction_received; do
    [ "$(cat "$trace_dir/events/$event/enable")" = 1 ] || {
        echo "Required event was not enabled: $event" >&2; exit 1;
    }
done
echo "Recording: repeat the stuttering gesture for $seconds seconds." >&2
sleep "$seconds"
printf '0\n' > "$trace_dir/tracing_on"
printf '\n=== buffer stats ===\n'
for node in "$trace_dir"/per_cpu/cpu*/stats; do read_node "$node"; done
printf '\n=== trace begin ===\n'
atrace --async_stop
printf '\n=== trace end ===\n'
[ "$(cat "$trace_dir/tracing_on")" = 0 ] || { echo 'Tracing is still on.' >&2; exit 1; }
[ "$(cat "$trace_dir/events/enable")" = 0 ] || { echo 'Trace events are still on.' >&2; exit 1; }
trace_owned=0
snapshot after
echo 'Finished. Trace events stopped; no performance settings changed.' >&2
