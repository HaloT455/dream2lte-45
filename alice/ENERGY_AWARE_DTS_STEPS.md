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
increments. The original Samsung DTS has 9 native A53 states (455–1690 MHz)
and 13 native M2 states (741–2314 MHz).

The older ALice high OPP limits are restored: **A53 2.002 GHz** and
**M2 2.704 GHz**, but these upper states are deliberately identified as
`OC_EST`, not native Samsung measured energy states. The governor
intersects with the real ACME/CAL frequency table, looks up ASV voltage
through `dev_pm_opp_find_freq_exact()`, and estimates extra busy power
relative to each cluster's last native DTS entry with `f * V^2`.
It never inserts a synthetic OPP or changes voltages to reach a target.
A missing OC OPP or voltage makes model initialization fail closed.
The `energy_steps` file labels each row `DTS` or `OC_EST`.
Estimated capacities above 1024 are private governor throughput units,
not a change to the scheduler's normalized global capacity.
Policy/thermal and native PM QoS bounds constrain the search before the driver.

See [the source-to-port mapping, full state tables and test details](../docs/ALICE-S8PLUS-ENERGYAWARE-A53-EGO-ESG.md).
The donor is pinned to commit `2ec382e83341d79b552e77e27505228c731e6459`.
Host tests and kernel/DTB compilation pass; physical S8+ boot and battery
measurements remain untested.
