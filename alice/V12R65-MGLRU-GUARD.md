# ALICE V12R65 — Adaptive MGLRU Guard (Samsung S8+ Exynos 8895)

## Control relationship

ALICE (userspace opt-in policy) -> /sys/kernel/mm/lru_gen/enabled -> MGLRU
(cpu memory page aging / cold-page reclaim). Android's LMKD remains independent
and can kill cached processes when its thresholds demand. MGLRU does **not**
manage CPU clocks, GPU shaders, LMKD daemon policy or application task priorities.

## Why the control is guarded

- User tested ALICE V12R61 boot on real SM-G955F and successfully switched
  MGLRU ON and OFF in a 15-second trial. A later longer period coincided with
  high SoC temperatures, reclaim no_progress/backoffs and reboot.
- These logs do not establish that MGLRU caused reboot or a kernel deadlock.
  The real underlying kernel stability problem has **not** been fixed.
- By default MGLRU remains OFF. This release does NOT enable MGLRU at boot.

## What V12R65 actually implements

- New packaged root helper alice_mglru_guard.sh and Java bridge
  AliceMglruGuard.java. Only status/probe/manual/auto/restore are permitted.
- Explicit user consent is required to enter experimental AI MGLRU control.
- General ALICE Resource Controller never authorizes MGLRU automatically.
- Only one 8-second automatic MGLRU trial per resource service session, if:
  - two samples 45 seconds apart show 5 <= PSI memory some avg10 < 22,
    PSI full avg10 < 2, MemAvailable >= 320,000 kB and <= 13% of total;
  - the root helper independently rechecks current PSI/available RAM;
  - recognizable CPU/GPU thermal zone values are <53 deg C;
  - battery sensor is present and reads <39 deg C;
  - MGLRU is OFF, Android boot has completed, and no paused guard exists.
- The trial writes enable=1 to the existing kernel switch, waits 8 seconds,
  returns to enable=0 and checks the kernel ALICE reclaim counters. When
  no_progress or backoffs increased, it creates a persistent auto-pause.
- Root helper uses an atomic directory lock and boot ID to recover stale
  locks following reboot. An emergency restore command explicitly writes
  enable=0 and verifies it.
- The manual trial also requires temperature checks and explicit double
  confirmation but does not require high PSI: it is a test, not an
  automatic reclaim policy.

## Important limitations

1. **No shell rollback, child process, Java service or watchdog can recover
   when the Linux kernel itself stops scheduling.** MGLRU may hang or
   reboot the phone despite an 8-second limit. Do not perform tests while
   charging with a hot SoC, or without backup.
2. This release reuses **ALICE V12R61 boot image**, unchanged; it does NOT
   claim to solve the underlying kernel MGLRU safety issue.
3. The trigger uses documented kernel pressure indicators with transparent
   deterministic rules. It does NOT mean pretrained Qwen3 has learned to
   operate the memory subsystem autonomously. Qwen3 still provides
   separate on-demand analysis and explanations only.
4. A LMKD process reclaim/kill is not initiated directly by MGLRU. The
   daemon makes its own decisions; old 'swap low' events require a separate
   evaluation of actual device policy and charging/thermal behavior.
5. CI build, APK checks and static shell tests do not certify S8+ runtime
   behavior. Keep normal resource controller ON only if its battery cost
   is justified by measured improvements.

## Reclaim data interpretation

The existing /sys/kernel/alice/mm_reclaim counters are cumulative and
cover instrumented reclaim paths; they are not all exclusive to MGLRU.
Even if scanned/reclaimed change, efficiency and performance cannot be
concluded without comparable before/after load, CPU time, PSI, refault
and thermal measurements.
