# Galaxy A53 EGO mechanism port to S8+: energy_aware only

This branch builds one CPUFreq governor: `energy_aware`. The strict Kconfig
profile masks every other CPUFreq governor and removes the performance fallback.
Generic inactive governor sources remain for other configurations; no schedutil
or compatibility energy_step object is linked into this S8+ profile.

## A53 source and port map

Donor: Samsung Galaxy A53 / Exynos1280, commit
[`2ec382e83341d79b552e77e27505228c731e6459`](https://github.com/s5e8825/android_kernel_samsung_s5e8825/commit/2ec382e83341d79b552e77e27505228c731e6459).
The archived `research/samsung-a53-exynos1280-ego-reference.c` matches the
pinned donor `kernel/sched/ems/ego.c`. Samsung's GPLv2 copyright is retained
in the ported model. The donor energy calculation also uses
[`energy_table.c`](https://github.com/s5e8825/android_kernel_samsung_s5e8825/blob/2ec382e83341d79b552e77e27505228c731e6459/kernel/sched/ems/energy_table.c).

| A53 mechanism | S8+ backport | Native adaptation |
| --- | --- | --- |
| `ego_find_energy_freq()` | `energy_aware_model.h` | Scan feasible OPPs, compute each energy, retain the minimum |
| `ego_compute_energy()` / `et_compute_cpu_energy()` | `energy_aware_model.h` | Per-CPU active plus CLKOFF/PWROFF idle time; Exynos8895 core/cluster costs |
| `ego_compute_cpu_idle_ratio()` / MLT | `energy_aware_idle.h` + `cpu_idle` trace callback | Eight 4 ms history buckets, shallow/deep idle residency |
| `et_freq_to_cap()` / `et_fill_energy_state()` | `eagov_build_model()` | Explicit native DTS frequency/capacity/power bindings intersected with driver OPPs |
| `fclamp` / driver constraints | `eagov_qos_range()` | Native ACME PM QoS classes read from DTS, policy min/max and thermal ceilings |
| EGO deferred driver update | `eagov_work()` | 4.4 IRQ/kthread transport, bounded replay and actual-OPP acknowledgement |

A53 EGO itself contains `get_next_freq()`, IOWAIT, up/down rate limits and a
utilization-derived floor. The energy mechanism is the OPP energy search and
active/idle prediction, not the absence of shared scheduler APIs. This port
keeps energy search always active, resolves its workload floor in capacity
states, and removes the donor's busy-only energy gate, eng-boost interpolation,
IOWAIT governor boost and directional frequency delays to meet this branch's
energy-aware-only requirement. It does not transplant the complete 5.10 EMS,
emstune, MHDVFS, SoMAC or Exynos1280 power coefficients into Linux 4.4.

## Selection and energy steps

`kernel/sched/energy_aware_model.h` contains the ported
`ego_find_energy_freq()` and `ego_compute_energy()`. The governor binds these
to scheduler events, native idle history, sysfs and the Exynos driver.
WALT supplies utilization when enabled; PELT includes RT accounting otherwise.
Deadline activity requests the highest modeled capacity, subject to effective
policy/QoS limits. Stale workload samples expire after a scheduler window.

Each candidate is an actual modeled operating state with explicit kHz,
capacity, core power and shared-cluster power. Unsupported driver frequencies
are skipped. Initialization rejects missing/malformed bindings and driver
ranges extending beyond the model. It does not select another governor or
calculate a proportional clock target when a model is missing.

For each state of capacity C, the port follows A53 EGO's normalized-time
mechanism separately for every CPU i. `R_i` is its observed CLKOFF fraction
among CLKOFF+PWROFF residency, on a 1024 scale:

```
active_i = min(work_i, C)
idle_i = C - active_i
clkoff_i = floor(idle_i * R_i / 1024)
pwroff_i = idle_i - clkoff_i

energy = sum(core_busy * active_i + core_idle * clkoff_i
             + core_pwroff * pwroff_i) / C
       + (cluster_busy * peak_work + cluster_idle * (C - peak_work)) / C
```

Peak work is capped to C for a saturated state. The final integer cost uses a
1024 scale. Core PWROFF power comes from the native DTS's second idle state.
Shared-cluster cost is counted once, using the native shallow-idle cost;
per-core PWROFF history does not prove that the whole shared cluster is off.
M2 cluster busy cost can be below its idle cost (35 versus 50), so both terms
are retained rather than dropping a negative busy-minus-idle difference.

Eight 4 ms history buckets retain actual `cpu_idle` entry/exit durations.
Exynos idle index 0 maps to CLKOFF/WFI; deeper states map to local PWROFF.
Remote snapshots use a per-CPU spinlock. Missing idle history charges shallow
idle cost conservatively and never disables energy selection. The source
tracepoint represents the requested cpuidle state; residency/boot behavior
still needs device validation. This replaces MLT's 5.10 event interfaces.

The native workload floor requires capacity ceil(9*peak_work/8), a 12.5%
headroom constraint. It is not a frequency formula or an assertion that A53's
emstune tunables are identical. Minimum predicted energy wins; ties favor lower
kHz. Overload selects the highest permitted modeled state. Native Samsung
PM QoS classes are read from each `cpufreq-domain`; their frequency bounds
constrain the search before calling the driver. A conflicting QoS floor yields
to the ceiling. The worker also detects externally changed/clamped frequencies
and does not report an unacknowledged state as applied.

A step change is a transition between these power/capacity states. Its power
jump is P(new)-P(old), where P=online_CPU_count*core_busy+cluster_busy. This is
a power difference in DTS units, not joules or a manually capped frequency
increment. Steps are always used. There is no disabled-by-default energy mode,
manual energy envelope, schedutil up/down delay, no-idle hold, IOWAIT boost or
fast-switch stub. The worker coalesces scheduler requests, checks driver success,
handles a new request arriving during a transition, and stops before policy
resources are freed. Driver/thermal/QoS transport is still necessary to apply
any governor's selected operating point.

## Frequency binding and range

The original `busy-cost-data` does not carry frequencies. `frequency-data`
now binds every core row to an explicit stock OPP, following the ordered
Exynos8895 domain/MIF OPP rows and their capacity ratios. This binding is a
source-level reconstruction, not a new hardware power measurement. Both
core and shared-cluster costs themselves are retained verbatim from the DTS.
Runtime initialization intersects these rows with the firmware driver's table.

The previous board override allowed A53 2002 MHz and M2 2704 MHz, beyond the
power model. It now limits A53 to 1690 MHz and M2 to 2314 MHz. Supporting higher
OPPs requires additional validated capacity/core-power/cluster-power rows;
reusing the last stock power row would underprice those OPPs.

The following busy-power columns assume four online CPUs; runtime diagnostics
use the current online policy count. Units are relative Samsung DTS costs.

### Cortex-A53

| Step | kHz | Capacity | Core | Cluster | Busy power | Jump from prior |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 455000 | 83 | 26 | 18 | 122 | 0 |
| 2 | 598000 | 108 | 33 | 21 | 153 | 31 |
| 3 | 715000 | 129 | 35 | 23 | 163 | 10 |
| 4 | 832000 | 151 | 43 | 24 | 196 | 33 |
| 5 | 949000 | 171 | 53 | 29 | 241 | 45 |
| 6 | 1053000 | 190 | 64 | 31 | 287 | 46 |
| 7 | 1248000 | 225 | 79 | 35 | 351 | 64 |
| 8 | 1456000 | 263 | 102 | 41 | 449 | 98 |
| 9 | 1690000 | 305 | 139 | 49 | 605 | 156 |

### Mongoose M2

| Step | kHz | Capacity | Core | Cluster | Busy power | Jump from prior |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 741000 | 328 | 152 | 35 | 643 | 0 |
| 2 | 858000 | 380 | 172 | 38 | 726 | 83 |
| 3 | 962000 | 426 | 192 | 39 | 807 | 81 |
| 4 | 1066000 | 472 | 216 | 43 | 907 | 100 |
| 5 | 1170000 | 518 | 240 | 45 | 1005 | 98 |
| 6 | 1261000 | 559 | 277 | 50 | 1158 | 153 |
| 7 | 1469000 | 651 | 377 | 62 | 1570 | 412 |
| 8 | 1703000 | 754 | 543 | 78 | 2250 | 680 |
| 9 | 1807000 | 800 | 624 | 87 | 2583 | 333 |
| 10 | 1937000 | 858 | 765 | 101 | 3161 | 578 |
| 11 | 2002000 | 886 | 841 | 114 | 3478 | 317 |
| 12 | 2158000 | 955 | 1148 | 149 | 4741 | 1263 |
| 13 | 2314000 | 1024 | 1469 | 174 | 6050 | 1309 |

## Runtime checks

All diagnostics are read-only. `energy_step` has changed from the old writable
optional envelope to the actual last driver-acknowledged state (0 before the
first successful transition). `energy_delta` records the last acknowledged
transition's power difference, and `predicted_energy` describes the latest
target. Driver/PM QoS clamping may temporarily leave the applied state unknown.

```sh
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    cat "$policy/scaling_available_governors"  # expected: energy_aware
    cat "$policy/scaling_governor"            # expected: energy_aware
    cat "$policy/energy_aware/energy_steps"
    cat "$policy/energy_aware/energy_step"
    cat "$policy/energy_aware/energy_delta"
    cat "$policy/energy_aware/idle_ratios"
done
```

## Verification

```sh
python3 scripts/test_alice_energy_step_dts.py
python3 scripts/test_energy_aware_worker.py
python3 scripts/check_energy_aware_only.py out/.config --system-map out/System.map
```

The host tests compile and execute the actual ported C selector and idle
history. Eight tests include 2400 randomized state/limit/workload/idle-ratio
comparisons against rational energy accounting, idle/overload, QoS/thermal
restrictions, tie breaking, shared-cluster accounting and changing power costs
at fixed work. A separate UBSan C harness executes the actual request/worker
functions with updates during driver calls, bounded replay, failures, externally
clamped OPPs, stop, stale/future peer timestamps, energy deltas and changing
native QoS floors/ceilings. Fixed work with different CLKOFF/PWROFF history is
also verified to select different OPPs.

The config/System.map checker rejects every other CPUFreq governor, including
performance fallback. CI repeats the tests and builds Image/DTBs. A local full
AArch64 GCC 14.2 build also passed and its linked map contains only
`cpufreq_gov_energy_aware`; the compiled DTB carries the explicit 9/13 state
bindings and 1690/2314 MHz maximums. The build retains an existing unrelated
crypto self-test section annotation warning (`testmgr_crypto_proc_init` ->
`crypto_init_proc`); no build error remains.

Compile and host-test success do not establish physical boot, responsiveness,
battery-life improvement or thermal stability. Those require an S8+ test.

Local validation build, 2026-11-23, Arm GNU Toolchain 14.2.Rel1, S8+
`exynos8895-dream2lte_defconfig` (source patch on `0833475d`):

| Output | SHA-256 of this local validation build |
| --- | --- |
| Image | `aede4eaf6e9cfd9525f7e2c1b4a6efb476db4243722bea966efff068daed4410` |
| dtb.img | `a44e89b6d4b49c6876f121778a9b390ca07b6270428d70271777d9bc6e1e1bd5` |

A separate Kconfig resolution test attempted to enable schedutil, the old
energy_step, interactive and performance alongside the strict flag. After
`olddefconfig` all four were rejected; only energy_aware remained.
