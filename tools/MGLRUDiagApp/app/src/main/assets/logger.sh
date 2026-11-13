#!/system/bin/sh

MODE="$1"
DIR="$2"
K="/sys/kernel/mm/lru_gen"
B="/sys/class/power_supply/battery"
M="/sys/bus/platform/devices/13900000.mali"

[ -n "$DIR" ] && mkdir -p "$DIR" || exit 2

boot_id() {
    cat /proc/sys/kernel/random/boot_id
}

session_boot_id() {
    sed -n 's/^boot_id=//p' "$DIR/session-info.txt" 2>/dev/null
}

read_node() {
    [ -r "$1" ] || return 0
    printf '%s=' "$1"
    cat "$1" 2>/dev/null
}

process_start() {
    awk '{ sub(/^.*\) /, ""); print $20 }' "/proc/$1/stat" 2>/dev/null
}

save_pid() {
    printf '%s %s\n' "$1" "$(process_start "$1")" > "$DIR/$2.pid"
}

stop_pid() {
    [ -r "$DIR/$1.pid" ] || return 0
    read -r pid start < "$DIR/$1.pid"
    case "$pid" in
        ''|*[!0-9]*) return 0 ;;
    esac
    if [ -n "$start" ] && [ "$start" = "$(process_start "$pid")" ]; then
        kill "$pid" 2>/dev/null
    fi
}

capture_state() {
    OUT="$1"
    {
        echo "===== DATE ====="
        date
        echo "===== UNAME ====="
        uname -a
        echo "===== BOOT ID ====="
        boot_id
        echo "===== UPTIME ====="
        cat /proc/uptime 2>/dev/null
        echo "===== MGLRU SYSFS ====="
        for f in enabled scan_around diag stats; do
            if [ -e "$K/$f" ]; then
                echo "--- $f ---"
                cat "$K/$f" 2>/dev/null
            fi
        done
        echo "===== MEMINFO ====="
        cat /proc/meminfo 2>/dev/null
        echo "===== PSI MEMORY ====="
        cat /proc/pressure/memory 2>/dev/null
        echo "===== SWAPS ====="
        cat /proc/swaps 2>/dev/null
        echo "===== POWER AND SWAP ====="
        awk '/^pswp(in|out) / {print}' /proc/vmstat
        for node in "$B/status" "$B/capacity" "$B/temp" "$B/chg_temp" \
            "$B/batt_current_ua_now" "$B/voltage_now" \
            /sys/block/zram0/comp_algorithm /sys/block/zram0/mm_stat; do
            read_node "$node"
        done
        if [ "$(cat "$B/status" 2>/dev/null)" = "Charging" ]; then
            read_node /sys/class/sec/switch/vbus_value
        fi
        for cpu in 0 4; do
            policy="/sys/devices/system/cpu/cpu$cpu/cpufreq"
            for node in scaling_governor scaling_min_freq scaling_max_freq \
                stats/time_in_state; do
                read_node "$policy/$node"
            done
        done
        echo "===== WIFI ====="
        read_node /sys/wifi/station_band
        cmd wifi status 2>/dev/null |
            sed -nE 's/.*RSSI: (-?[0-9]+).*Frequency: ([0-9]+).*/rssi_dbm=\1 frequency_mhz=\2/p'
        echo "===== MALI ====="
        read_node "$M/core_mask"
        read_node "$M/halo_probe"
        echo "===== CAMERA VENDOR ====="
        for f in /vendor/etc/alice-test7/camera-feature.xml \
            /vendor/lib64/hw/camera.universal8895.so; do
            [ ! -r "$f" ] || sha256sum "$f" 2>/dev/null
        done
        if [ -r /vendor/etc/alice-test7/camera-feature.xml ]; then
            grep -E 'name="SUPPORT_(SCENE_OPTIMIZER|PHOTO_NIGHT)"' \
                /vendor/etc/alice-test7/camera-feature.xml 2>/dev/null
        fi
        echo "===== PROPS ====="
        for key in ro.build.version.release ro.build.version.sdk \
            ro.vendor.build.fingerprint sys.boot_completed sys.boot.reason \
            init.svc.lmkd ro.lmk.use_psi; do
            printf '%s=%s\n' "$key" "$(getprop "$key" 2>/dev/null)"
        done
    } > "$OUT" 2>&1
}

capture_postboot() {
    current="$(boot_id)"
    original="$(session_boot_id)"
    [ -n "$current" ] && [ -n "$original" ] && [ "$current" != "$original" ] || return 0
    TARGET="$DIR/postboot/boot-$current"
    mkdir -p "$DIR/postboot" || return 1
    mkdir "$TARGET" 2>/dev/null || return 0
    date > "$TARGET/capture-time.txt" 2>&1
    cat /proc/uptime > "$TARGET/uptime.txt" 2>&1
    printf '%s\n' "$current" > "$TARGET/boot-id.txt"
    uname -a > "$TARGET/uname.txt"

    if [ -r /proc/last_kmsg ]; then
        cat /proc/last_kmsg > "$TARGET/last_kmsg.txt" 2>&1
    fi

    if [ -d /sys/fs/pstore ]; then
        mkdir -p "$TARGET/pstore"
        cp -f /sys/fs/pstore/* "$TARGET/pstore/" 2>/dev/null
    fi

    return 0
}

case "$MODE" in
start)
    capture_state "$DIR/state-before.txt"

    {
        echo "session_started=$(date '+%Y-%m-%d %H:%M:%S %z')"
        echo "scan_around=$(cat "$K/scan_around" 2>/dev/null)"
        echo "diag=$(cat "$K/diag" 2>/dev/null)"
        echo "boot_id=$(boot_id)"
    } > "$DIR/session-info.txt"

    cat > "$DIR/memory-loop.sh" <<'EOF'
#!/system/bin/sh
K="/sys/kernel/mm/lru_gen"
B="/sys/class/power_supply/battery"
while true; do
    echo "===== $(date '+%Y-%m-%d %H:%M:%S.%3N %z') ====="
    awk '/^(MemFree|MemAvailable|Active|Inactive|SwapTotal|SwapFree):/ {print}' /proc/meminfo
    awk '/^pswp(in|out) / {print}' /proc/vmstat
    cat /proc/pressure/memory 2>/dev/null
    for f in temp batt_current_ua_now; do
        if [ -r "$B/$f" ] && read -r value < "$B/$f"; then
            printf '%s=%s\n' "$f" "$value"
        fi
    done
    if [ -e "$K/stats" ]; then
        cat "$K/stats" 2>/dev/null
    fi
    echo
    sleep 2
done
EOF
    chmod 700 "$DIR/memory-loop.sh"

    nohup dmesg -w > "$DIR/dmesg-live.txt" 2>&1 < /dev/null &
    save_pid "$!" dmesg

    nohup logcat -v threadtime -b all -T 1 -f "$DIR/logcat-live.txt" \
        -r 4096 -n 2 > "$DIR/logcat-error.txt" 2>&1 < /dev/null &
    save_pid "$!" logcat

    nohup sh "$DIR/memory-loop.sh" > "$DIR/memory-live.txt" 2>&1 < /dev/null &
    save_pid "$!" memory
    ;;

stop)
    current="$(boot_id)"
    if [ -n "$current" ] && [ "$current" = "$(session_boot_id)" ]; then
        for p in dmesg logcat memory; do
            stop_pid "$p"
        done
    fi

    capture_state "$DIR/state-stop.txt"

    if [ -e "$K/stats" ]; then
        cat "$K/stats" > "$DIR/mglru-stats-final.txt" 2>&1
    fi

    dmesg > "$DIR/dmesg-final.txt" 2>&1
    logcat -t 4000 -v threadtime -b all > "$DIR/logcat-final.txt" 2>&1
    capture_postboot
    ;;

postboot)
    capture_postboot
    ;;

*)
    echo "usage: $0 {start|stop|postboot} SESSION_DIR" >&2
    exit 2
    ;;
esac

exit 0
