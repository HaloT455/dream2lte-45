# ALice energy_aware: DTS-backed energy steps (Exynos8895 / Linux 4.4)

## What is real and what is reused

The governor `kernel/sched/cpufreq_energy_aware.c` reuses Linux 4.4
schedutil's scheduler update hooks, WALT/PELT utilization inputs, IOWAIT
handling, kthread frequency transitions and up/down rate limits.
**Those mechanisms do not determine the target frequency.**

The target frequency is selected by `eagov_energy_model_freq()`:
- Read Samsung `sched-energy-costs` tables (`sge_array`) loaded from
  `arch/arm64/boot/dts/exynos/exynos8895.dtsi`.
- Apply demand/capacity headroom, then inspect actual driver OPP frequencies
  inside `policy->min` / `policy->max`.
- Estimate core (SUM load) + shared cluster (PEAK load) energy from DTS
  busy/idle power costs and model capacity states.
- Select minimum predicted energy among OPPs satisfying demanded capacity.
- An optional `energy_step` selects a **DTS power-state envelope**, not
  equally spaced MHz increments. A manual absolute `energy_power_budget`
  may tighten that envelope. Both are soft constraints: capacity required
  by scheduler workload takes priority when no feasible OPP lies inside
  the power envelope.

Unlike Exynos1280 Android 13's full Samsung EGO/EMS, this Linux 4.4
adaptation does **not** port `emstune`, `et_compute_cpu_energy()`,
`fclamp`, `et_freq_to_cap()` or MLT idle ratios. The OPP frequency-to-
capacity conversion remains an approximation because this DT exposes
capacity/power pairs without explicit frequency for each pair.

## energy_step tunable

`energy_step=0` (default): automatic minimum-energy OPP search, no manual
power ceiling. `energy_step=1..N`: use the actual DTS power of state N,
counting from the lowest-power state, as an upper power envelope.
Oversized values clamp to the final state in a cluster (writes above 32
are rejected).

The step is evaluated separately for each cluster:

| CPU group | DTS table | Steps | Example full-cluster busy cost |
|---|---|---|---|
| CPU0-3 Cortex-A53 | CPU_COST_1 + CLUSTER_COST_1 | 1..9 | step 1: 122, step 3: 163, step 9: 605 |
| CPU4-7 Exynos M2 | CPU_COST_0 + CLUSTER_COST_0 | 1..13 | step 1: 643, step 13: 6050 |

Costs are in **the DTS model's relative units**, not measured milliwatts.
The shared-cluster cost is added once, core cost once per CPU.

Read active config after boot (paths vary by per-policy vs global governor):
```sh
for x in /sys/devices/system/cpu/cpufreq/policy*/energy_aware/energy_step \
         /sys/devices/system/cpu/cpufreq/energy_aware/energy_step; do
  if [ -f "$x" ]; then echo "$x = $(cat "$x")"; fi
done
for x in /sys/devices/system/cpu/cpufreq/policy*/scaling_governor; do
  echo "$x = $(cat "$x")"
done
```

Changing `energy_step` may affect burst performance; it does not override
thermal, voltage, QoS or hardware limits. Always measure CPUFreq traces,
temperature, application responsiveness and energy on-device.

## Verification

CI executes `python3 scripts/test_alice_energy_step_dts.py` before
building. The test parses the real DTS power pairs and validates A53/M2
power envelopes and the governor's use of the budget/energy search.
It is **not** runtime validation or proof of battery-life improvements.

The compiled source is directly linked via
`CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYAWARE=y`; `energy_step` is a tunable
inside `energy_aware`, *not* the separate legacy `energy_step` governor.
