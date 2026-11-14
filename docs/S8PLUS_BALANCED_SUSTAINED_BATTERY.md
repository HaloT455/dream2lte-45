# ALice S8+ — Balanced Sustained Battery (experimental)

Base: `agent/s8plus-v12r69-reverse-energy-game-lz4kd-20261114`.

Target: Galaxy S8+ Exynos 8895 SM-G955F, Linux 4.4.302 with WALT-backed EAS and independent ALice `energy_step` governor. Do not imply this is Exynos2100 Samsung EMS energy_step.

## Why
The previous energy_step governor selects the lowest sufficient step at very low utilization, but applies 12.5% frequency headroom to other utilization. In sustained medium-load usage that can keep the costly M2 cluster at a higher OPP than necessary. Conversely, removing all headroom hurts rendering bursts and game startup.

## What changed
- Utilization below 75% of capacity: cap requested headroom to 6.25% of base frequency, then quantize to the existing 8 driver steps.
- Utilization at/above 75%: keep the former 12.5% headroom for game-entry bursts and responsiveness.
- Keep a previous OPP at moderate load only when it still meets current demand and does not exceed the new moderate headroom target.
- Preserve independent A53 and M2 CPUFreq policies, schedutil fallback, RT/DL handling, IOWAIT boost, 3 ms up and 12 ms down update limits.
- No additional userspace poller, wake lock, overclock, voltage changes or disabling of thermal throttling.

## Unchanged
- Full Mali-G71 MP20 graphics resources: `CONFIG_MALI_HALO_NPU_PARTITION` disabled.
- CPU-based LZ4KD ZRAM; ROM may change compressor at init. Confirm `[lz4kd]` in `/sys/block/zram0/comp_algorithm` before claiming runtime use.
- PSI + Android userspace LMKD; no duplicate legacy kernel LMK.
- Exynos VPU is a specialized vision processor, **not** an emulated general-purpose NPU.
- Samsung original thermal, battery protection and all existing CPU/GPU OPP limits.
- MGLRU behavior inherited unchanged from the base; existing One UI device-specific risks remain.

## Validation
Host tests compare 1025 utilization points across A53/M2 between previous and balanced heuristics. A full ARM64 compile and boot/recovery validation are separate gates. Static tests are not proof of improved battery life, FPS or temperature.

On the **same ROM and conditions**, collect governor states, thermal zones, GPU frequency, PSI, LMKD, and ZRAM using `scripts/collect_s8plus_game_perf.sh`. Then compare 15-30 minute sessions, FPS/frame time percentiles, temperature and battery change. Do not suppress Samsung thermal throttling or hold performance governor continuously.

Do not flash until boot is repacked using a confirmed bootable S8+ ramdisk and DTB/board identity are verified. Keep a byte-for-byte copy of the original boot.
