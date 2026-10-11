# V12R5U: MGLRU donor audit (SM-G955F Exynos8895, 2026-10-11)

## Research ranking and verified source status

| Repo | Board/SoC | Kernel | Tested MGLRU source? | Reuse scope |
|---|---|---|---|---|
| ace2nutzer/Samsung_dreamlte_Kernel | S8/S8+/Note8 Exynos8895 | 4.4.111 | NO lru_gen symbols in default mm/vmscan.c, no Kconfig LRU_GEN | Exynos8895 Samsung reclaim assumptions only |
| TheGalaxyProject/tgpkernel-s8-p | S8/S8+ Exynos8895 | 4.4.180 | NO in default mm/vmscan.c/Kconfig | Native 4.4 ABI and device memory layout only |
| duhansysl/exynos9810-kernel | S9/Note9 Exynos9810 | 4.9.337 | NO in default mm/vmscan.c/Kconfig | Samsung platform and memory pressure behaviour only |
| crdroidandroid/android_kernel_samsung_universal9611 | A51 Exynos9611 (4xA73+4xA53) | 4.14.364-openela | YES: mm/Kconfig LRU_GEN, mm/vmscan.c lru_gen_age_node and lru_gen_shrink_lruvec; a51_defconfig LRU_GEN=y and LRU_GEN_ENABLED=y | **Primary algorithmic reference, not binary donor** |
| krazey/common | mainline Exynos9810 platform | 7.1 development tree | YES: mm/vmscan.c native modern LRU_GEN and exynos9810-starlte_defconfig flags | Reference only; vastly different MM ABI |

## Invariant mismatch — why no direct source transplant

V12R5T is Samsung **Linux 4.4.302 per-zone**: `lruvec_zone(lruvec)->lru_lock`, lru size indexed by generation/type/zone, legacy `shrink_page_list()`, Samsung LMKD+PSI; current MGLRU defaults OFF until runtime validated. The Exynos9611 4.14 backport is **per-node**: `lru_gen_age_node(pgdat, sc)`, has different LRU list and memcg structures, different migration/accounting and mmwalk support. Preserve V12R5T native platform drivers, KSU, vendor init, schedutil, thermal, swap/zRAM and per-zone reclaim ABI. Never flash kernel images from a different device.

## Targeted V12R5U stability repairs already isolated

- Under zone->lru_lock, derive **current** lruvec max_seq for page-table aging; do not use `args->max_seq` snapshot after a potentially sleeping mmap walk. This prevents assigning a sampled page into an already-recycled generation.
- Under zone->lru_lock, recheck live MGLRU enabled state before rmap scan-around while the sysfs runtime switch may be moving all lists. Keep scan-around and ptwalk opt-in until on-device stress is conclusive.
- Do **not** make MGLRU enable by default yet: V12R5M–T logs show repeated no-progress reclaim, zone counters/list reconciliation and LMKD aggression in prior testing. Compiling fixes does not establish device stability.

## Objective gates to claim finished

1. CI arm64 Image/dtb for enforcing and permissive must compile, plus MGLRU static regression tests.
2. On-device with V12R5T known-good rollback: enable MGLRU in a bounded diagnostic session; verify generation ages, reclaim scanned/reclaimed, absence of empty-oldest storms, misplaced counters, softdog, kernel panic, critical process eviction.
3. Compare PSI memory full/some and LMKD victims + zRAM free space / swap pressure with MGLRU OFF vs ON under matched use; adjust only measured pressure/aging path. Ensure charging, thermal, Wi-Fi/BT, UI scrolling and suspend/resume are preserved.
4. Only when reproducible real-device results pass should default-enabled MGLRU be considered.

Sources: https://github.com/crdroidandroid/android_kernel_samsung_universal9611 ; https://github.com/ace2nutzer/Samsung_dreamlte_Kernel ; https://github.com/TheGalaxyProject/tgpkernel-s8-p ; https://github.com/duhansysl/exynos9810-kernel ; https://github.com/krazey/common
