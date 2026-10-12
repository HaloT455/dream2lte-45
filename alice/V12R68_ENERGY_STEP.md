# ALICE V12R68 EnergyStep-compatible governor (Exynos 8895, Linux 4.4)

## Scope
This is an independent CPUFreq governor whose sysfs name is `energy_step`.
It is **not the original Samsung Exynos 2100 EMS energy_step implementation**.
Samsung's donor `kernel/sched/ems/energy_step.c` is coupled to Linux 5.4
Energy Management Scheduler, emstune, uclamp, power tables and vendor-specific
scheduler hooks missing from the S8+ 4.4 tree.

Rather than copying unportable code or renaming schedutil, V12R68:
- Starts from the proven S8+ WALT/PELT utilization-update pipeline;
- Computes a raw utilization-dependent clock with 12.5% headroom;
- Quantizes frequency to 8 discrete steps within the cpufreq policy min/max,
  then resolves an actual driver-supported OPP;
- Retains explicit 3ms up and 12ms down delay limits with a worker thread;
- Retains IOWAIT boost, deadline-task handling and cpufreq slow-path synchronization;
- Never disables thermal, QoS, watchdog or existing CPU frequency bounds;
- Builds schedutil as a separate available fallback governor.

This governor optimizes frequency selection heuristically. It does NOT
use the original EMS power tables and cannot guarantee improved battery life,
gaming FPS, multitasking app survival or lower thermal load.

## Default and real-device verification
New defconfig: CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYSTEP=y
Fallback compiled: CONFIG_CPU_FREQ_GOV_SCHEDUTIL=y
MGLRU default: CONFIG_LRU_GEN_ENABLED=y
V12R67 One UI early-init MGLRU compatibility retained.

After boot, CHECK actual active governors (ROM might override the default):

```sh
adb shell 'su -c "
uname -r
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  [ -f \"\$p/scaling_governor\" ] || continue
  echo \"=== \$p ===\"
  cat \"\$p/scaling_governor\"
  cat \"\$p/scaling_available_governors\"
  cat \"\$p/scaling_cur_freq\"
done
cat /sys/kernel/mm/lru_gen/enabled
cat /sys/kernel/mm/lru_gen/lru_gen_boot_compat
"'
```

If actual active governor is schedutil and energy_step appears in
scaling_available_governors, the ROM overrode boot default. Investigate its
policy; DO NOT repeatedly write the governor without diagnosing root cause.

## Revert governor WITHOUT reflashing (if responsive)

```sh
adb shell 'su -c "
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  [ -w \"\$p/scaling_governor\" ] || continue
  echo schedutil > \"\$p/scaling_governor\"
done
"'
```

For bootloop or unresponsive kernel, flash a verified V12R66/V12R61 BOOT
image through TWRP. Changing governor will not prevent MGLRU kernel deadlock
or fix application-kill policy of One UI 8.

## Required before daily use

CI compile + kernel/System.map + DTB + boot header SHA-1 checks must pass.
Then test on SM-G955F: early boot, all CPU policies, frequencies, thermal
throttling, app switching, suspend/resume, charging and at least one hour
of representative usage. Compare to V12R66 on the same charger and workloads.

Do NOT describe this as fully Samsung Energy Step or a stable daily driver
before hardware results.
