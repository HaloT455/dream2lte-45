#!/system/bin/sh
# Optional root userspace bridge for ALice S8+ kernel emergency request.
# One UI proprietary maximum power saver requires a privileged ROM integration.
# Never spoof battery SOC, set voltages/current, change thermal or normal CPU/GPU.
STATE=/sys/kernel/alice_battery_reserve/upsm_locked
LOGTAG=ALiceBatteryReserve
read_lock() {
    [ -r "$STATE" ] || return 1
    IFS= read -r current < "$STATE" || return 1
    [ "$current" = 0 ] || [ "$current" = 1 ] || return 1
    printf '%s' "$current"
}
ensure_saver() {
    present=$(settings get global low_power 2>/dev/null)
    [ "$present" = 1 ] && return 0
    cmd power set-mode 1 >/dev/null 2>&1 || true
    new=$(settings get global low_power 2>/dev/null)
    if [ "$new" != 1 ]; then
        settings put global low_power 1 >/dev/null 2>&1 || true
    fi
}
[ "$(id -u 2>/dev/null)" = 0 ] || exit 1
while [ "$(getprop sys.boot_completed 2>/dev/null)" != 1 ]; do sleep 5; done
last=unknown
while :; do
    locked=$(read_lock) || { sleep 15; continue; }
    if [ "$locked" = 1 ]; then
        [ "$last" = 1 ] || log -t "$LOGTAG" "emergency locked: enforce Android saver" 2>/dev/null
        ensure_saver
        sleep 15
    else
        [ "$last" = 1 ] && log -t "$LOGTAG" "kernel emergency released" 2>/dev/null
        # Normal mode never touches power/CPU/GPU settings; do not overwrite
        # an Android user's separately chosen normal battery-saver preference.
        sleep 30
    fi
    last=$locked
done
