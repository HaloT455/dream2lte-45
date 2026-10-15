# One-shot startup/end configuration only; never run in the periodic sampler.
PATH=/system/bin:/system/xbin:/vendor/bin:/sbin
export PATH LC_ALL=C
read_node() {
    [ -r "$1" ] || return 0
    printf '\n@@ %s\n' "$1"
    count=0
    while IFS= read -r line || [ -n "$line" ]; do
        printf '%s\n' "$line"
        count=$((count+1))
        [ "$count" -lt "${2:-4096}" ] || { printf '[LINE_LIMIT]\n'; break; }
    done < "$1"
    return 0
}
printf '@@ kernel\n'
uname -r
printf '\n@@ ROM (no fingerprint or device serial)\n'
for n in ro.build.version.release ro.build.version.sdk ro.product.model; do printf '%s=' "$n"; getprop "$n"; done
read_node /data/adb/alice-cpu-compat/status.log 120
read_node /data/adb/alice-powerhal/status.log 120
printf '\n@@ Power HAL service\n'
getprop init.svc.vendor.samsung.power-default
dumpsys -t 2 android.hardware.power.IPower/default 2>/dev/null
read_node /sys/power/alice_power_hint
printf '\n@@ task profile digests (read errors retained)\n'
/system/bin/toybox sha256sum /system/etc/task_profiles.json /vendor/etc/task_profiles.json 2>&1
read_node /system/etc/task_profiles.json
read_node /vendor/etc/task_profiles.json
printf '\n@@ actual cpuset topology and permissions\n'
ls -ldZ /dev/cpuset /dev/cpuset/cpus /dev/cpuset/sf /dev/cpuset/sf/cpus 2>&1
for f in /dev/cpuset/cpus /dev/cpuset/*/cpus; do read_node "$f"; done
for f in /sys/devices/system/cpu/cpufreq/energy_step/*rate* /sys/devices/system/cpu/cpufreq/policy*/energy_step/*rate* /sys/power/cpufreq_min_limit /sys/power/cpufreq_max_limit /sys/power/cpufreq_table /dev/stune/*/schedtune.boost /dev/stune/*/schedtune.prefer_idle; do read_node "$f"; done
printf '\n@@ LMKD tuning (existing properties only)\n'
getprop | while IFS= read -r line; do
    case "$line" in '[ro.lmk.'*|'[persist.device_config.lmkd_native.'*) printf '%s\n' "$line";; esac
done
if [ "$end_snapshot" = 1 ]; then
    printf '\n@@ selected error counts in last 400 system log entries (not session totals)\n'
    logcat -d -b system -t 400 -v brief 2>/dev/null | (
        cpuset_errors=0
        while IFS= read -r line; do
            case "$line" in *'Failed to write'*'/dev/cpuset/cpus'*) cpuset_errors=$((cpuset_errors+1));; esac
        done
        printf 'cpuset_root_write_errors=%s\n' "$cpuset_errors"
    )
fi
printf '\n@@ foreground package at snapshot (not full usage history)\n'
pkg=$(dumpsys -t 2 activity activities 2>/dev/null | while IFS= read -r line; do
    case "$line" in *mResumedActivity:*|*topResumedActivity=*)
        for token in $line; do
            case "$token" in */*) candidate=${token%%/*};
                case "$candidate" in ''|*[!A-Za-z0-9_.]*) ;; *) printf '%s\n' "$candidate"; break 2;; esac;;
            esac
        done;;
    esac
done)
printf '%s\n' "$pkg"
for target in com.android.systemui "$pkg"; do
    [ -n "$target" ] || continue
    case "$target" in *[!A-Za-z0-9_.]*) continue;; esac
    printf '\n@@ gfxinfo summary %s (snapshot only; cumulative, no reset)\n' "$target"
    dumpsys -t 2 gfxinfo "$target" 2>/dev/null | while IFS= read -r line; do
        case "$line" in *'Stats since:'*|*'Total frames rendered:'*|*'Janky frames:'*|*'Janky frames (legacy):'*|*'percentile:'*) printf '%s\n' "$line";; esac
    done
done
exit 0
