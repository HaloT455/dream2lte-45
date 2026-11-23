# A53 EGO energy-aware mechanism on S8+

The current implementation ports A53 EGO's OPP energy search and per-CPU
active/CLKOFF/PWROFF prediction to S8+ Linux 4.4. Energy search always runs.
It uses the S8+'s own capacity/core/cluster power states and eight 4 ms native
idle-history buckets; Exynos1280 power coefficients are not copied.

`CONFIG_CPU_FREQ_ENERGY_AWARE_ONLY=y` builds and registers only `energy_aware`.
No schedutil, compatibility energy_step, interactive or performance governor
is linked. Generic inactive governor sources remain available to other configs.

| Runtime file under each policy's `energy_aware/` | Meaning |
| --- | --- |
| `energy_steps` | All native frequency/capacity/power steps and adjacent power jumps |
| `energy_step` | Last driver-acknowledged step, read-only |
| `energy_delta` | Last acknowledged transition's busy-power difference |
| `predicted_energy` | Latest target's normalized-window predicted cost |
| `idle_ratios` | Per-CPU CLKOFF/PWROFF shares on a 1024 scale |

The former writable `energy_step` soft envelope and `energy_power_budget`
mode are removed. Steps are mandatory energy-model states, not arbitrary MHz
increments. A53 has 9 modeled states (455–1690 MHz), M2 has 13
(741–2314 MHz). Those are the ranges with native DTS energy data.
Policy/thermal and native PM QoS bounds constrain the search before the driver.

See [the source-to-port mapping, full state tables and test details](../docs/ALICE-S8PLUS-ENERGYAWARE-A53-EGO-ESG.md).
The donor is pinned to commit `2ec382e83341d79b552e77e27505228c731e6459`.
Host tests and kernel/DTB compilation pass; physical S8+ boot and battery
measurements remain untested.
