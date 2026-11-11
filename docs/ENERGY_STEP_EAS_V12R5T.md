# V12R5T ESG2 AFC A/B test

This branch builds on the ESG1 commit
`f7f411468a27d812a6ea239e8143c1ae0526d14b`. The supplied reference boot is
`V12R5T-Enforcing-BOOT.img`, SHA-256
`80c3f368ac934725aa1bae01529646c339ade3b88b656e4f98670ba71a850043`.
It contains WALT, SchedTune, energy-aware scheduling and the legacy DT
`sched-energy-costs` tables. Its default governor is schedutil.

## Implementation and provenance

This is an experimental 8895 adaptation of the power-step idea, not the full
Samsung EMS/PART/emstune implementation. The scheduler update hooks, IOWAIT,
rate limiting, per-policy worker and lifecycle come from this branch's
`cpufreq_schedutil.c` (Intel 2016, GPL-2.0). The power budget follows
`find_step_power()` and `find_allowed_capacity()` in Samsung's Exynos850 EMS
code, as published in [this pinned 4.19 source](https://github.com/physwizz/a127f-T-u9/blob/028e98770c5934feb865fa6320c75ea42d993b45/kernel/sched/ems/energy.c).

The new `energy_step` governor reads the existing per-core capacity/power
table from `sge_array[cpu][SD_LEVEL0]`. It rejects missing, zero-capacity,
unsorted-capacity and decreasing-power models. Its experimental power increment
is one eighth of the model's min/max power span. It estimates active time as
frequency-invariant utilization divided by current capacity, capped at 100%.
This replaces the newer Samsung PART history dependency; it is an estimate,
not a measurement of active time or battery power.

This build uses the ESG1 Energy Step capacity calculation with the ESG2
Zstandard configuration. Energy Step applies the ESG1 utilization headroom
and power-model boost whenever utilization is positive, within the current
policy limits. This isolates the scheduler change for a device charging test.
Compare VBUS and battery current after charging settles with the same adapter,
cable, battery level, temperature and screen state.
The same calculation feeds legacy EAS's capacity prediction. A sequence-counted
snapshot contains only the immutable boot-time energy-table pointer and scalar
policy values, never a pointer to an allocation freed when switching governor.
Stopping the governor drains updates/work before disabling its predictor;
schedutil then uses the original EAS prediction path.

Frequency requests go through the existing Exynos ACME slow path and driver
resolution. Thermal/QoS ceilings remain authoritative. CI selects energy_step
as the boot default and also compiles schedutil for comparison.

## ZRAM and memory pressure

ZRAM defaults to Zstandard level 1 with a workspace sized for page compression.
The library and xxHash come from Linux 4.19.325 at
`a67e7cdde7cc7984ae24c3c81a70dc1aa34424b1`. The adapter uses the synchronous
compression API in this 4.4 kernel.

The kernel provides memory cgroups, PSI triggers and pidfd syscalls for
Android's LMKD service. Both kernel LMK drivers are disabled. The ROM's
userspace service and PSI settings determine the active policy after boot.

## Model limits

The legacy DT tables contain capacity/power pairs, not explicit frequency or
voltage pairs. Energy Step maps normalized capacity to the driver's maximum frequency
and resolves the resulting request to a supported OPP. This is an approximation.
In particular, existing overclocked OPPs are not independently power-calibrated.
EAS still rounds to its legacy capacity states, while hardware follows the
driver's OPP table and thermal/QoS constraints. Runtime boosts and transition
delays can also make instantaneous frequency differ from the estimate.

Consequently this build does not establish energy savings, Samsung EMS parity,
or device stability. Upstream EAS documents support for schedutil; this older
vendor experiment adds its own predictor and must be validated separately:
[upstream EAS requirements](https://docs.kernel.org/scheduler/sched-energy.html#dependencies-and-requirements-for-eas).

## CI and device checks

The dedicated workflow builds only the enforcing variant. It executes host C
tests of the shared math, EAS model-index bounds, the existing worker regression
suite and the baseline integration checks. It then builds Image/DTB and checks
the new governor/predictor symbols in System.map. CI output includes the exact
config, map, build log and SHA-256 checksums. CI success is compilation evidence.

Repack Image/DTB into the supplied reference boot with the existing
`scripts/repack_boot_v0.py`; retain that original boot for comparison. Physical
checks should establish both clusters' governor selection, driver-applied
min/max, thermal behavior, display suspend/resume, camera, repeated app launch
and representative UI frame times. Compare energy consumed over the same
completed workload at the same starting temperature, brightness and radio state.
No performance or power improvement is claimed before these measurements.

Useful read-only checks after boot:

```sh
uname -a
cat /sys/block/zram0/comp_algorithm /proc/swaps
getprop init.svc.lmkd
getprop ro.lmk.use_psi
cat /proc/pressure/memory
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_min_freq
cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq
```
