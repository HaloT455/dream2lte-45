# Xiaomi budget-device MGLRU comparison for Galaxy S8+ V12R5T (RESEARCH ONLY)

Date 2026-10-11. K510 Linux 5.10 is **on hold**. This branch starts from the pinned known-good `agent/v12r5t-mglru-aging-stability` (commit `3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3`); do not modify that base branch or flash any build from this note.

## Reference 1 — actual low-end Xiaomi device, Redmi 10C (fog/wind/rain)

- Official 4 GiB variants, Snapdragon 680, Android MIUI 13 base: https://www.mi.com/cl/product/redmi-10c/specs/
- Community source: https://github.com/r0ddty/kernel_xiaomi_fog/tree/andromeda-mk2; Linux 4.19.328 in Makefile, not an official Xiaomi released boot image.
- Exact active MGLRU config in source: https://github.com/r0ddty/kernel_xiaomi_fog/blob/andromeda-mk2/arch/arm64/configs/vendor/fog-perf_defconfig
  - CONFIG_PSI=y; CONFIG_MEMCG=y; CONFIG_MEMCG_SWAP=y;
  - CONFIG_LRU_GEN=y; CONFIG_LRU_GEN_ENABLED=y;
  - CONFIG_ZSMALLOC=y; CONFIG_ZRAM=y; CONFIG_HAVE_USERSPACE_LOW_MEMORY_KILLER=y.
- Config is SOURCE evidence only: the phone's shipped ROM or any specific user device needs /proc/config.gz, /sys/kernel/mm/lru_gen and its actual boot image for runtime proof.
- In fog custom 4.19 mm/vmscan.c there are lru_gen_min_ttl_ms, multi-bit enabled caps, page-table look-around, per-lruvec age walker, MGLRU-owned reclaim. File: https://github.com/r0ddty/kernel_xiaomi_fog/blob/andromeda-mk2/mm/vmscan.c
- This particular 4.19 fork defaults min_ttl to 5*HZ (5000ms), and the source can invoke the OOM killer when the protected working set cannot fit. DO NOT copy 5000ms; Linux upstream MGLRU docs recommend caution above 1000ms, especially on memory-constrained hardware: https://docs.kernel.org/admin-guide/mm/multigen_lru.html

## Reference 2 — newer Xiaomi community 4.14 backport

- https://github.com/vantoman/kernel_xiaomi_sm6150/tree/14 has Linux 4.14.328 plus MGLRU in mm/Kconfig and mm/vmscan.c.
- Example enabled 7 generations, LZ4 zRAM, and in-kernel Simple LMK in **individual custom configurations**, not proof all Xiaomi variants use them: https://github.com/vantoman/kernel_xiaomi_sm6150/blob/14/arch/arm64/configs/davinci_defconfig
- `CONFIG_LRU_GEN=y`, `CONFIG_LRU_GEN_ENABLED=y`, `CONFIG_NR_LRU_GENS=7`, `CONFIG_ZRAM=y`, `CONFIG_ZRAM_DEF_COMP_LZ4=y`, `CONFIG_ANDROID_SIMPLE_LMK=y`.
- Important contrast: Simple LMK is NOT equivalent to Android's PSI userspace lmkd. Do not enable two LMK engines in V12R5T.

## Negative controls — Xiaomi kernels without an MGLRU Kconfig in inspected branch

- Community Redmi Note 11 spes kernel 4.19.325: https://github.com/crdroidandroid/android_kernel_xiaomi_spes/tree/16.0 (mm/Kconfig lacked CONFIG_LRU_GEN in the checked branch).
- Redmi 9A dandelion open source 4.9.190: https://github.com/redmi-mt6765-dev/android_kernel_xiaomi_dandelion/tree/dandelion-q-oss (no MGLRU Kconfig in checked branch).
- They commonly employ other combinations of classic reclaim, zRAM and lowmemorykiller. We cannot infer all ROMs or official Xiaomi firmware behavior from these individual forks.

## Audited working Galaxy S8+ V12R5T state

- Source https://github.com/HaloT455/dream2lte-45/tree/agent/v12r5t-mglru-aging-stability
- Linux 4.4.302, 7 generations, 4 tiers, `CONFIG_LRU_GEN=y`, **`# CONFIG_LRU_GEN_ENABLED is not set`**, stats Kconfig disabled.
- `CONFIG_PSI=y`, `CONFIG_MEMCG=y`, `CONFIG_MEMCG_SWAP=y`, `CONFIG_ZRAM=y`.
- Both `CONFIG_ANDROID_LOW_MEMORY_KILLER` and `CONFIG_ANDROID_SIMPLE_LMK` are unset: Android userspace lmkd can be the single process-kill authority, contingent on verified runtime properties.
- Runtime V12R5T sysfs interface is bespoke: `/sys/kernel/mm/lru_gen/enabled` only accepts **0 or 1**; independently `scan_around`, `ptwalk`, `diag`, `stats` nodes. **No upstream-style bitmap 0x0007** or `min_ttl_ms` node. Do not blindly run Xiaomi scripts on this 4.4 tree.
- Scan-around, ptwalk and verbose diag default to false; ptwalk explicitly refuses direct-reclaim walks and is meant for guarded kswapd testing.
- V12R5T `mm/vmscan.c` contains an original 4.4 *legacy reclaim bridge*: MGLRU selects aging/cold candidates, but Samsung 4.4's shrink_page_list remains the pageout engine. It differs from the more native 4.19 fork and needs under-pressure correctness tests, not only idle benchmarking.
- V12R5T's runtime LRU toggle converts lists between two reclaim models. Changing this under pressure is riskier than a boot-time-on setting once the implementation is stable. **Do not set boot-time enabled while reclaim bugs are still possible.**

## Conservative engineering direction

1. Keep pinned V12R5T source/working BOOT untouched and K510 paused. Make isolated minimal experimental changes only after reviewing vmscan's per-lruvec generation floor and the 4.4 classic shrink_page_list bridge.
2. Treat Xiaomi 10C fog as comparative architecture only: use fast PSI + MEMCG + zRAM and one userspace lmkd; avoid copying Simple LMK and custom `min_ttl_ms=5000`.
3. Audit V12R5T risks around per-lruvec backoff, reclaim target delta, refault accounting, aging starvation and page lock contention. Preserve rollback if direct reclaim stalls.
4. Establish baseline and pressure comparability using read-only procfs/sysfs `memory PSI`, `vmstat` (pgscan, pgsteal, pswpin/out, workingset_refault), zRAM compressed pages, `lru_gen/stats`, lmkd kill counts and full CPU/temperature/battery traces. Measurements require the running **4.4 V12R5T system**, not TWRP or K510.
5. Only after accounting and no-progress guards pass should a guarded 4.4 experimental build consider MGLRU boot enabled. Do not claim flash-ready or measured speedups without build + real-device data.

Reference official Android PSI LMKD: https://source.android.com/docs/core/perf/lmkd ; memory reclaim/LMKD interaction: https://developer.android.com/topic/performance/memory/guide/kswapd-lmkd-interaction .
