PATH=/system/bin:/system/xbin:/vendor/bin:/sbin
export PATH LC_ALL=C
printf '@@ kernel\n'
uname -r
printf '\n@@ ROM (no fingerprint or device serial)\n'
for n in ro.build.version.release ro.build.version.sdk ro.product.model; do
    printf '%s=' "$n"; getprop "$n"
done
printf '\n@@ CPU/GPIS compatibility status\n'
if [ -r /data/adb/alice-cpu-compat/status.log ]; then tail -40 /data/adb/alice-cpu-compat/status.log; fi
printf '\n@@ Power HAL bootstrap status\n'
if [ -r /data/adb/alice-powerhal/status.log ]; then tail -40 /data/adb/alice-powerhal/status.log; fi
printf '\n@@ Power HAL service\n'
getprop init.svc.vendor.samsung.power-default
dumpsys -t 2 android.hardware.power.IPower/default 2>/dev/null | head -c 4096
printf '\n@@ kernel Power HAL state\n'
cat /sys/power/alice_power_hint 2>/dev/null
printf '\n@@ actual cpuset topology\n'
for f in /dev/cpuset/cpus /dev/cpuset/*/cpus; do
    [ -r "$f" ] || continue
    printf '%s=' "$f"; cat "$f"
done
printf '\n@@ EnergyStep rates\n'
for f in /sys/devices/system/cpu/cpufreq/energy_step/*rate* /sys/devices/system/cpu/cpufreq/policy*/energy_step/*rate*; do
    [ -r "$f" ] || continue
    printf '%s=' "$f"; cat "$f"
done
printf '\n@@ LMKD tuning (existing properties only)\n'
getprop | awk '/^\[(ro\.lmk\.|persist\.device_config\.lmkd_native\.)/ {print}'
exit 0
