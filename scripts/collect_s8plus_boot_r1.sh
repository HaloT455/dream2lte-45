#!/system/bin/sh
# Read-only snapshot. Run after reproducing a screen-off flash or charger attach.
# sh /data/local/tmp/collect_s8plus_boot_r1.sh wall > /sdcard/ALice-wall.txt
label=${1:-snapshot}
show() {
    [ -r "$1" ] || return 0
    printf '\n[%s]\n' "$1"
    cat "$1" 2>/dev/null || true
}
printf 'ALice boot R1 snapshot: %s\n' "$label"
date
uname -a
show /proc/uptime
show /proc/sys/vm/swappiness
show /sys/kernel/mm/lru_gen/enabled
show /sys/power/cpufreq_min_limit
show /sys/power/cpufreq_max_limit
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$policy" ] || continue
    for field in affected_cpus scaling_driver scaling_governor scaling_min_freq \
        scaling_max_freq cpuinfo_min_freq cpuinfo_max_freq cpuinfo_cur_freq \
        scaling_cur_freq scaling_available_frequencies stats/time_in_state \
        energy_aware/oc_status energy_aware/energy_states; do
        show "$policy/$field"
    done
done
for supply in /sys/class/power_supply/*; do
    [ -d "$supply" ] || continue
    for field in type online status health voltage_now current_now voltage_max \
        current_max input_current_limit input_voltage_limit usb_type charge_type \
        capacity temp hv_charger_status batt_charging_source; do
        show "$supply/$field"
    done
done
for field in state water lpm_mode cur_version; do
    show "/sys/class/sec/ccic/$field"
done
for field in lcd_type power alpm; do
    show "/sys/class/lcd/panel/$field"
done
show /sys/class/graphics/fb0/blank
for light in /sys/class/backlight/*; do
    [ -d "$light" ] || continue
    for field in brightness actual_brightness max_brightness; do
        show "$light/$field"
    done
done
printf '\n[filtered kernel events]\n'
dmesg 2>/dev/null | grep -iE \
    'energy_aware|lru_gen|panel|decon|dsim|ccic|s2mm|pdo|pdic|power_list|sec_bat|muic|afc|max77865' \
    | tail -n 600
