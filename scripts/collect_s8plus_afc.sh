#!/system/bin/sh
# Read-only AFC/charge/temperature report for the Galaxy S8+.
# Never write charger current, health, voltage, MUIC register or thermal sysfs.
echo "=== S8+ AFC read-only check ==="
date
echo "device: $(getprop ro.product.device)"
echo "kernel: $(uname -r)"
for p in /sys/class/power_supply/*; do
 [ -d "$p" ] || continue
 echo "[$p]"
 for key in type online status health voltage_now current_now \
    input_current_limit constant_charge_current charge_type temp \
    capacity technology voltage_max usb_type fast_charging_enabled \
    current_max input_voltage_regulation; do
   [ -r "$p/$key" ] && printf '%s=' "$key" && cat "$p/$key"
 done
done
for node in /sys/class/thermal/thermal_zone*; do
 [ -r "$node/type" ] && [ -r "$node/temp" ] && \
  echo "thermal $(cat "$node/type"): $(cat "$node/temp")"
done
echo "=== Android charge properties ==="
for key in sys.boot_completed init.svc.lmkd ro.boot.hardware; do
 echo "$key=$(getprop "$key")"
done
echo "=== AFC diagnostics are read-only. No changes made. ==="
