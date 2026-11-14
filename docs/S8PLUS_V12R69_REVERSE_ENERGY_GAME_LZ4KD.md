# Galaxy S8+ dream2lte — V12R69 Reverse Energy Step game experiment

**Status: experimental kernel source; NOT flash-ready or verified on a phone.**
Base: `agent/v12r69-systemui-mglru-lmkd-stability`. Do not modify the existing boot baseline.
Target: Exynos8895 SM-G955F, 4x Cortex-A53 CPU0–3 + 4x Mongoose M2 CPU4–7, Mali-G71 MP20.

## Inverse heuristic — not fake Samsung Energy Step
Real Samsung Energy Step from Exynos2100 EMS is not directly portable to Linux 4.4.
This branch changes the existing independent `energy_step` CPUFreq implementation:
1. Compute **minimum viable** OPP from utilization without extra frequency headroom;
2. Compute **burst** OPP with 12.5% headroom;
3. On low load, choose the minimum viable OPP, especially for the M2 cluster;
4. At moderate load, retain a previous frequency only when it can satisfy the current demand;
5. On high load choose the burst OPP promptly; existing rate limits remain 3ms up / 12ms down;
6. Preserve RT/DL handling, IOWAIT boost, hotplug, thermal/QoS and the CPUFreq worker.

This is the *reverse of boost-first selection*, **not** an ML controller, true runtime energy-model optimization, or a frame-time predictor. Loading screens may bottleneck on storage or shader compilation. FPS and battery improvement require real measurements.

## GPU and VPU
Disable `CONFIG_MALI_HALO_NPU_PARTITION`, restoring the driver's normal full Mali-G71 shader scheduling to graphics/game workloads. The earlier 15 graphics/5 compute split was experimental; it does NOT manufacture a neural accelerator. Keep `CONFIG_EXYNOS_VPU=y` and `CONFIG_EXYNOS_VPU_HARDWARE=y`: Samsung VPU supports firmware/driver-defined image/vision functions. **There is no general NNAPI/TFLite NPU backend or ability to render 3D games on the VPU**. Adding one needs actual firmware and userspace integration.

## Memory
Port the CPU-based LZ4KD crypto encoder/decoder and configure `CONFIG_ZRAM_DEF_COMP_LZ4KD=y`. The ROM may override before activating ZRAM; check `cat /sys/block/zram0/comp_algorithm` and expect `[lz4kd]`. Never reset a live ZRAM swap device. Preserve Android userspace LMKD with `CONFIG_PSI=y`, `CONFIG_MEMCG=y` and kernel old/simple LMK off; verify `init.svc.lmkd=running`. Do not disable vendor LMKD / Chimera.

## Thermals and battery
Keep Samsung stock TMU, GPU throttle, charging protections and CPU voltage/OPPs. No overclock or artificial raised thermal trip. Unverified until data collection in a sustained game (15-30 minutes, temperature, frame times, frequency residency and power). If the chip approaches thermal throttling, lower graphics quality or FPS cap; a kernel cannot bypass power physics.

## Verification / rollback
```sh
adb shell cat /sys/block/zram0/comp_algorithm
adb shell 'for p in /sys/devices/system/cpu/cpufreq/policy*; do cat "$p/scaling_governor"; done'
adb shell getprop init.svc.lmkd
adb push scripts/collect_s8plus_game_perf.sh /data/local/tmp/alice_s8_game_perf.sh
adb shell sh /data/local/tmp/alice_s8_game_perf.sh > s8plus-game-baseline.txt
```
No host `su`: use `adb shell su -c ...` to request phone-side root, if necessary.

The CI tests do not prove a bootable image or stable daily use. Keep a complete known-good boot backup and a recovery path. Test only once a matching ramdisk/DTB/ROM combination has been verified.
