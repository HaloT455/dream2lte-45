# ALice S8+ `energy_aware` — A53 Samsung EGO/ESG adaptation

## Upstream sources (GPLv2)

* **Samsung Exynos1280 / Galaxy A53 EGO**: original `kernel/sched/ems/ego.c` from [s5e8825 unified](https://github.com/s5e8825/android_kernel_samsung_s5e8825/blob/s5e8825-unified/kernel/sched/ems/ego.c), archived here as `research/samsung-a53-exynos1280-ego-reference.c`.
* **Original Samsung ESG `energy_step.c` supplied by the tester**: archived verbatim at `research/samsung-energy_step-user-reference.c`.

These archived source files are references **and are not compiled** into the S8+ kernel. Their original GPLv2 headers are preserved.

## What actually runs on Exynos8895 / Linux 4.4.302

The registered built-in CPUFreq governor remains **`energy_aware`**, implemented by `kernel/sched/cpufreq_energy_aware.c`; it is **not called `energy_step` or `schedutil`**.

The real logic:
1. Receive per-CPU scheduler utilization and handle IOWAIT, RT/DL and shared-policy workload aggregation.
2. Compute a *minimum feasible capacity* with 12.5% headroom.
3. Walk every valid OPP in the driver's `policy->freq_table`, just as A53 EGO scans CPU frequency entries.
4. Read the native Exynos8895 DTS `sched-energy-costs` tables for per-core and shared-cluster busy/idle power.
5. Estimate the workload's dynamic and idle energy at each feasible OPP; select the lowest predicted-energy OPP. Tie goes to the lower frequency. Thermal and driver policy limits are obeyed.
6. Apply the existing Linux 4.4 slow cpufreq driver workqueue and separate up/down hysteresis limits.

There is **no** `get_next_freq()` multiplying CPU utilization by max frequency to request a proportional `schedutil` frequency.

## The user's `energy_step.c`: optional step-power budget

Samsung ESG uses `find_step_power()` and `find_allowed_capacity()`, which depend on the EMS energy table and emstune nodes absent in this kernel. To carry that capability **inside `energy_aware`**, we implement sysfs **`energy_power_budget`** in Exynos8895 DTS busy-cost units:

- Default **0 = disabled**; the EGO-like minimum-energy search remains active and fully functional.
- Positive values: the governor prefers the minimum-energy OPP whose **four core busy powers + shared cluster busy power** fall below the budget, provided it can satisfy CPU workload capacity.
- If the budget cannot satisfy capacity or thermal limits, the ordinary feasible minimum-energy OPP wins; no forced undervolting or out-of-range frequency.
- This is a *port of the step-power idea*, **not** a claim that Samsung's exact `find_step_power()` or A53 emstune is present.

For a running policy, inspect paths resembling:

```sh
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor
cat /sys/devices/system/cpu/cpufreq/policy4/scaling_governor
cat /sys/devices/system/cpu/cpufreq/policy0/energy_aware/energy_power_budget
```

Do not enable an arbitrary budget without first profiling the S8+; power units differ by DTS/core type.

## Scope and caveats

This is a **native energy-aware CPUFreq governor adapted from genuine A53 EGO and Samsung ESG source**, not a full Linux 5.10 Samsung EMS/EGO subsystem. The A53 kernel also has `et_fill_energy_state`, `et_compute_cpu_energy`, MLT idle-state ratios, `emstune`, `fclamp`, and cooperative task placement, which do not exist in this Linux 4.4 source. Core+cluster idle costs are estimates rather than actual A53 MLT history. The resulting firmware may have different behavior despite compiling.

Legacy governor sources can remain in the source tree for build-system compatibility, but the **target defconfig compiles neither `CONFIG_CPU_FREQ_GOV_SCHEDUTIL` nor `CONFIG_CPU_FREQ_GOV_ENERGYSTEP`**; the `energy_aware` governor is built in and default. KernelSU and LZ4KD remain enabled.

The GitHub CI compilation verifies symbols and config, **not physical boot, battery life or thermal stability**. Keep the known-good S8+ boot image and recovery access before testing new experimental kernels.
