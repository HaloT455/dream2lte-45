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


## Full ALice EGO candidate tables: 455–2002 / 741–2704 MHz

The existing Samsung `frequency-data` / `busy-cost-data` pairs are preserved.
Only the new **`oc-frequency-data`** property declares additional candidate
frequencies. The governor checks each high OPP against the real ACME CAL table
and reads that chip's ASV voltage. It estimates only the extra busy-power
coefficients using the **f × V²** dynamic-power relationship. These
coefficients are **not original Samsung power measurements**.

| # | A53 (kHz) | Cost source | M2 (kHz) | Cost source |
|---|---:|---|---:|---|
| 1 | 455000 | DTS | 741000 | DTS |
| 2 | 598000 | DTS | 858000 | DTS |
| 3 | 715000 | DTS | 962000 | DTS |
| 4 | 832000 | DTS | 1066000 | DTS |
| 5 | 949000 | DTS | 1170000 | DTS |
| 6 | 1053000 | DTS | 1261000 | DTS |
| 7 | 1248000 | DTS | 1469000 | DTS |
| 8 | 1456000 | DTS | 1703000 | DTS |
| 9 | 1690000 | DTS | 1807000 | DTS |
| 10 | 1794000 | OC_EST | 1937000 | DTS |
| 11 | 1898000 | OC_EST | 2002000 | DTS |
| 12 | 2002000 | OC_EST | 2158000 | DTS |
| 13 | — | — | 2314000 | DTS |
| 14 | — | — | 2496000 | OC_EST |
| 15 | — | — | 2574000 | OC_EST |
| 16 | — | — | 2652000 | OC_EST |
| 17 | — | — | 2704000 | OC_EST |

`DTS` here means the **original cost coefficients**; the correspondence
between frequency and a native cost row is the earlier ALice reconstruction,
not an independently measured Samsung calibration.

The sysfs `energy_steps` table shows which rows were actually installed
at boot and marks each `DTS` or `OC_EST`. An unsupported OC row is
**skipped with a warning**, not fabricated. Thermal/PM QoS limits remain
effective; an advertised top-frequency candidate does not mean that the
processor must or can sustain it.

To see real runtime results (requires root):

```sh
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  echo "$p: $(cat "$p/scaling_governor")"
  cat "$p/energy_aware/energy_steps" 2>/dev/null
done
dmesg | grep -E 'energy_aware:.*(OC|EGO)'
```

Host regression: `python3 scripts/test_alice_oc_states.py` validates
all 12 + 17 frequency entries and the C cost estimator. The final
CI build must compile an Image and DTB; real boot remains a separate test.

