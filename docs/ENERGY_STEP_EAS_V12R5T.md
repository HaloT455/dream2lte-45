# V12R5T ESG1 LZ4KD recovery test

This kernel builds from ESG1 commit
`f7f411468a27d812a6ea239e8143c1ae0526d14b`. Repack it with
`V12R5T-ESG1-EnergyStep-EAS-Enforcing-TEST.img`, SHA-256
`ecd162faf3bec9e9b9380b818e4abf2ac05ea2a30edc02967a16338c0f92d95b`.
ESG1 uses WALT, SchedTune, Energy Step and legacy EAS.

## Memory and accelerators

The CPU compresses and decompresses ZRAM pages with LZ4KD. Its existing
per-CPU stream, same-filled-page and full-page storage paths handle swap.
This port uses the Huawei codec from the [HarmonyOS source
import](https://github.com/tew080/android_kernel_ginkgo/commit/03c3cfeb904aea43991d4a828b2bc7621e934380).
The adapter uses a bounded workspace and rejects malformed compressed pages.

The kernel exposes PSI, memcg, swap accounting and pidfds for Android LMKD.
The ROM starts and configures the daemon. Both kernel LMK implementations
are disabled. The earlier watchdog log showed generation-list inconsistencies
after enabling MGLRU. This build uses classic reclaim so runtime scripts
cannot re-enable that path. The existing ZRAM CMA migration remains enabled.

The Mali driver uses its normal shader masks and DVFS. The Exynos VPU retains
its VS4L interface for compatible vision workloads. Dispatching an AI model
to the VPU requires a userspace client that supplies a supported graph.

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

The target is the greater of the baseline 25% utilization headroom and the
power-step capacity scaled by that busy estimate, clamped to policy limits.
The same calculation feeds legacy EAS's capacity prediction. A sequence-counted
snapshot contains only the immutable boot-time energy-table pointer and scalar
policy values, never a pointer to an allocation freed when switching governor.
Stopping the governor drains updates/work before disabling its predictor;
schedutil then uses the original EAS prediction path.

Frequency requests go through the existing Exynos ACME slow path and driver
resolution. Thermal/QoS ceilings remain authoritative. CI selects energy_step
as the boot default and also compiles schedutil for comparison. The repository
defconfig stays at its original default so other builds do not silently change.

## Model limits

The legacy DT tables contain capacity/power pairs, not explicit frequency or
voltage pairs. ESG1 maps normalized capacity to the driver's maximum frequency
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

Repack Image/DTB into the ESG1 reference boot with the existing
`scripts/repack_boot_v0.py`; retain that original boot for comparison. Physical
checks should establish both clusters' governor selection, driver-applied
min/max, thermal behavior, display suspend/resume, camera, repeated app launch
and representative UI frame times. Compare energy consumed over the same
completed workload at the same starting temperature, brightness and radio state.
No performance or power improvement is claimed before these measurements.

Useful read-only checks after boot:

```sh
uname -a
getprop init.svc.lmkd
getprop ro.lmk.use_psi
getprop sys.boot.reason
cat /proc/pressure/memory /proc/swaps /proc/sys/vm/swappiness
cat /sys/block/zram0/comp_algorithm /sys/block/zram0/io_stat /sys/block/zram0/mm_stat
cat /sys/bus/platform/devices/13900000.mali/core_mask
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_min_freq
cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq
```
