#!/system/bin/sh

MODE="$1"
DIR="$2"
K="/sys/kernel/mm/lru_gen"

mkdir -p "$DIR"

capture_state() {
    OUT="$1"
    {
        echo "===== DATE ====="
        date
        echo "===== UNAME ====="
        uname -a
        echo "===== BOOT ID ====="
        cat /proc/sys/kernel/random/boot_id 2>/dev/null
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
        echo "===== PROPS ====="
        getprop ro.build.version.release 2>/dev/null
        getprop ro.build.version.sdk 2>/dev/null
        getprop sys.boot_completed 2>/dev/null
    } > "$OUT" 2>&1
}

collect_postmortem() {
    TARGET="$1"
    mkdir -p "$TARGET"
    date > "$TARGET/capture-time.txt" 2>&1
    cat /proc/uptime > "$TARGET/uptime.txt" 2>&1
    cat /proc/sys/kernel/random/boot_id > "$TARGET/boot-id.txt" 2>&1

    dmesg > "$TARGET/dmesg-current.txt" 2>&1
    logcat -d -v threadtime -b all > "$TARGET/logcat-current.txt" 2>&1

    if [ -r /proc/last_kmsg ]; then
        cat /proc/last_kmsg > "$TARGET/last_kmsg.txt" 2>&1
    fi

    if [ -d /sys/fs/pstore ]; then
        mkdir -p "$TARGET/pstore"
        cp -f /sys/fs/pstore/* "$TARGET/pstore/" 2>/dev/null
    fi

    capture_state "$TARGET/state.txt"
    sync
}

case "$MODE" in
start)
    echo "$$" > "$DIR/start-shell.pid"
    capture_state "$DIR/state-before.txt"

    if [ -e "$K/diag" ]; then
        echo 1 > "$K/diag"
    fi
    if [ -e "$K/stats" ]; then
        echo 0 > "$K/stats"
    fi

    {
        echo "session_started=$(date '+%Y-%m-%d %H:%M:%S %z')"
        echo "scan_around=$(cat "$K/scan_around" 2>/dev/null)"
        echo "diag=$(cat "$K/diag" 2>/dev/null)"
        echo "boot_id=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)"
    } > "$DIR/session-info.txt"

    cat > "$DIR/memory-loop.sh" <<'EOF'
#!/system/bin/sh
DIR="$1"
K="/sys/kernel/mm/lru_gen"
N=0
while true; do
    echo "===== $(date '+%Y-%m-%d %H:%M:%S.%3N %z') ====="
    cat /proc/meminfo 2>/dev/null | grep -E 'MemFree:|MemAvailable:|Active:|Inactive:|Active\(anon\):|Inactive\(anon\):|Active\(file\):|Inactive\(file\):|SwapTotal:|SwapFree:'
    cat /proc/pressure/memory 2>/dev/null
    if [ -e "$K/stats" ]; then
        cat "$K/stats" 2>/dev/null
    fi
    echo
    N=$((N + 1))
    if [ $((N % 16)) -eq 0 ]; then
        sync
    fi
    sleep 0.25
done
EOF
    chmod 700 "$DIR/memory-loop.sh"

    logcat -c 2>/dev/null

    nohup dmesg -w > "$DIR/dmesg-live.txt" 2>&1 < /dev/null &
    echo $! > "$DIR/dmesg.pid"

    nohup logcat -v threadtime -b all > "$DIR/logcat-live.txt" 2>&1 < /dev/null &
    echo $! > "$DIR/logcat.pid"

    nohup sh "$DIR/memory-loop.sh" "$DIR" > "$DIR/memory-live.txt" 2>&1 < /dev/null &
    echo $! > "$DIR/memory.pid"

    sleep 1
    sync

    if [ -e "$K/enabled" ]; then
        echo 1 > "$K/enabled"
    fi

    capture_state "$DIR/state-after-enable.txt"
    sync
    ;;

stop)
    if [ -e "$K/enabled" ]; then
        echo 0 > "$K/enabled" 2>/dev/null
    fi

    capture_state "$DIR/state-stop.txt"

    for p in dmesg logcat memory; do
        if [ -r "$DIR/$p.pid" ]; then
            PID="$(cat "$DIR/$p.pid" 2>/dev/null)"
            if [ -n "$PID" ]; then
                kill "$PID" 2>/dev/null
            fi
        fi
    done

    sleep 1

    if [ -e "$K/stats" ]; then
        cat "$K/stats" > "$DIR/mglru-stats-final.txt" 2>&1
    fi

    dmesg > "$DIR/dmesg-final.txt" 2>&1
    logcat -d -v threadtime -b all > "$DIR/logcat-final.txt" 2>&1

    collect_postmortem "$DIR/postmortem-stop"
    sync
    ;;

postboot)
    mkdir -p "$DIR/postboot"
    COUNT=1
    while [ -e "$DIR/postboot/boot-$COUNT" ]; do
        COUNT=$((COUNT + 1))
    done
    collect_postmortem "$DIR/postboot/boot-$COUNT"
    ;;

*)
    echo "usage: $0 {start|stop|postboot} SESSION_DIR" >&2
    exit 2
    ;;
esac

exit 0
