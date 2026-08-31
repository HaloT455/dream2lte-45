#!/system/bin/sh
# App-owned config and pre-created output; no trace text travels through Java.
# Perfetto drains ftrace continuously and writes a bounded binary file.
set -eu
umask 077
[ "$#" = 3 ] || { echo 'Expected config, pre-created output and owned native output.'; exit 2; }
config=$1
output=$2
native_output=$3
[ -f "$config" ] && [ -f "$output" ] && [ ! -L "$config" ] && [ ! -L "$output" ] || exit 2
native_name=${native_output##*/}
token=${native_name#alice-ui-}
token=${token%.perfetto-trace}
case "$token" in ''|*[!a-f0-9-]*) echo 'Invalid session token.'; exit 2 ;; esac
[ "${#token}" = 36 ] &&
    [ "$native_output" = "/data/misc/perfetto-traces/alice-ui-$token.perfetto-trace" ] || exit 2
[ -d /data/misc/perfetto-traces ] || { echo 'ROM has no Perfetto output directory.'; exit 2; }
[ ! -e "$native_output" ] && [ ! -L "$native_output" ] || {
    echo 'Native output already exists; never overwrite another log.'; exit 2;
}
grep -Fxq -- "output_path: \"$native_output\"" "$config" || exit 2
[ "$(id -u)" = 0 ] || { echo 'Run through su.'; exit 2; }
command -v perfetto >/dev/null || { echo 'ROM has no perfetto. No settings changed.'; exit 2; }

trace_dir=
mounted_here=0
child=
interrupted=0
owned_child() {
    [ -n "$child" ] && [ -r "/proc/$child/cmdline" ] &&
        tr '\000' '\n' < "/proc/$child/cmdline" | grep -Fxq -- "$config"
}
stop_child() {
    if owned_child; then kill -TERM "$child" 2>/dev/null || true; fi
}
interrupt() { interrupted=1; stop_child; }
cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    if owned_child; then
        stop_child
        # Never forcibly stop a shared traced service or clear global events.
        echo 'ALICE_CLEANUP_UNCONFIRMED: owned perfetto still running; reboot before another capture.'
        result=1
    fi
    if [ "$mounted_here" = 1 ]; then
        if [ "$(cat "$trace_dir/events/enable")" = 0 ]; then
            umount "$trace_dir" || { echo 'Temporary tracefs mount remains until reboot.'; result=1; }
        else
            echo 'ALICE_CLEANUP_UNCONFIRMED: events remain enabled; no forced reset.'
            result=1
        fi
    fi
    exit "$result"
}
trap cleanup EXIT
trap interrupt HUP INT TERM

for candidate in /sys/kernel/tracing /sys/kernel/debug/tracing; do
    if [ -e "$candidate/trace_marker" ]; then trace_dir=$candidate; break; fi
done
if [ -z "$trace_dir" ]; then
    trace_dir=/sys/kernel/tracing
    [ -d "$trace_dir" ] || { echo 'No tracefs mount point. Install UI1-Trace.'; exit 1; }
    awk '$NF == "tracefs" { ok=1 } END { exit !ok }' /proc/filesystems || exit 1
    if awk -v p="$trace_dir" '$2 == p { ok=1 } END { exit !ok }' /proc/mounts; then
        echo 'Trace path mounted but unusable. Do not change SELinux.'; exit 1
    fi
    mount -t tracefs -o nosuid,nodev,noexec tracefs "$trace_dir" || exit 1
    mounted_here=1
fi
[ "$(cat "$trace_dir/current_tracer")" = nop ] &&
    [ "$(cat "$trace_dir/events/enable")" = 0 ] || {
    echo 'Another trace is active. Save/stop it first.'; exit 1;
}
for prop in debug.atrace.tags.enableflags debug.atrace.app_number debug.atrace.user_initiated; do
    case "$(getprop "$prop")" in
        ''|0|0x0|false) ;;
        *) echo "Another trace session is active ($prop)."; exit 1 ;;
    esac
done

read_node() {
    [ -r "$1" ] || return 0
    printf '\n[%s]\n' "$1"
    cat "$1" || true
}
snapshot() {
    printf '\n=== %s ===\n' "$1"
    for node in /proc/uptime /proc/meminfo /proc/vmstat /proc/swaps \
        /proc/sys/kernel/sched_cpu_ui_hints /proc/sys/kernel/sched_sync_hint_enable \
        /sys/kernel/mm/lru_gen/enabled \
        /sys/class/power_supply/battery/status /sys/class/power_supply/battery/temp \
        /sys/class/thermal/thermal_zone*/type /sys/class/thermal/thermal_zone*/temp \
        /dev/cpuctl/*/cpu.ui_hint_boost /dev/cpuctl/*/cpu.ui_hint_prefer_idle; do
        read_node "$node"
    done
    for cpu in 0 4; do
        for name in scaling_cur_freq scaling_min_freq scaling_max_freq; do
            read_node "/sys/devices/system/cpu/cpu$cpu/cpufreq/$name"
        done
    done
    for app in com.sec.android.app.launcher com.android.systemui; do
        for pid in $(pidof "$app" 2>/dev/null || true); do
            read_node "/proc/$pid/cgroup"
        done
    done
}

echo 'ALice UI Trace 1.1; Perfetto binary; requested duration=60000 ms'
echo "NATIVE_OUTPUT=$native_output"
uname -r
getenforce
perfetto --version
snapshot before
[ "$interrupted" = 0 ] || exit 130
echo 'ALICE_STARTING'
# Android 11+ traced creates this file in its allowed directory. Do not pass
# an app-private fd: enforcing traced cannot generally write app_data_file.
perfetto --txt -c "$config" &
child=$!
if [ "$interrupted" = 1 ]; then stop_child; fi
started=0
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1 &
    timer=$!
    wait "$timer" || true
    [ "$interrupted" = 0 ] || break
    kill -0 "$child" 2>/dev/null || break
    if [ "$(cat "$trace_dir/events/sched/sched_switch/enable")" = 1 ] &&
       [ "$(cat "$trace_dir/events/sched/sched_wakeup/enable")" = 1 ] &&
       [ "$(cat "$trace_dir/events/vmscan/mm_vmscan_direct_reclaim_begin/enable")" = 1 ] &&
       [ "$(cat "$trace_dir/events/vmscan/mm_vmscan_direct_reclaim_end/enable")" = 1 ]; then
        started=1
        echo 'ALICE_RECORDING'
        break
    fi
done
if [ "$started" = 0 ]; then
    echo 'Required scheduler/reclaim events did not start. Check Perfetto service/permissions; do not change SELinux.'
    stop_child
fi
result=0
wait "$child" || result=$?
# wait can return on a shell signal before the child has finished flushing.
while owned_child; do
    wait "$child" || result=$?
done
child=
echo 'ALICE_SAVING'
snapshot after
echo '=== ftrace stats after (Perfetto end stats are authoritative) ==='
for node in "$trace_dir"/per_cpu/cpu*/stats; do read_node "$node"; done
echo "PERFETTO_EXIT_CODE=$result"
echo "CAPTURE_CANCELLED=$interrupted"
[ "$(cat "$trace_dir/events/enable")" = 0 ] || {
    echo 'ALICE_CLEANUP_UNCONFIRMED: events remain enabled; no forced reset.'; exit 1;
}
# Import only the exact session output after the native writer has stopped.
# On copy failure leave the native file and its path in the TXT for recovery.
if [ -f "$native_output" ] && [ ! -L "$native_output" ]; then
    cp "$native_output" "$output" || { echo 'Native trace retained: import failed.'; exit 1; }
    rm -- "$native_output" || { echo 'Native trace duplicate retained: cleanup failed.'; exit 1; }
fi
# Perform owned-mount cleanup before claiming success.
if [ "$mounted_here" = 1 ]; then umount "$trace_dir" || exit 1; mounted_here=0; fi
echo 'ALICE_CLEANUP_OK'
[ "$interrupted" = 0 ] || exit 130
[ "$started" = 1 ] && [ "$result" = 0 ] && [ -s "$output" ] || exit 1
echo 'ALICE_CAPTURE_COMPLETE'
