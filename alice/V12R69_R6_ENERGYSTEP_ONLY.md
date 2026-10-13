# V12R69 R6: direct EnergyStep, schedutil removed

The user requests complete removal of schedutil and direct use of EnergyStep.
This removes `cpufreq_schedutil.c`, its build/default-governor hooks, its
Kconfig options, its dedicated test and the obsolete workflows that build it.
Historical refs retain those older releases and workflows.

SchedTune was selected by EnergyStep but still depended on schedutil. Its
dependency now describes the shared CPU-frequency/SMP infrastructure.
Frequency-variant SchedTune depends directly on EnergyStep. Both remain
enabled in the S8+ configuration; deleting schedutil must not silently drop
these boost/utilization features. UI performance capture now reads the
EnergyStep tunables. No source-level alias or forwarding call to schedutil
is used; EnergyStep owns its scheduler hooks, worker, tunables and DVFS calls.

EnergyStep retains the R5 fixes, WALT/PELT/IOWAIT, hardware frequency steps,
112.5% headroom, 3/12 ms up/down rate limits and policy/thermal/QoS constraints.
EAS placement margin is unchanged. `performance` remains the standard cpufreq
fallback if governor initialization fails; schedutil is no longer available.

MGLRU remains default ON. The lean APK is unchanged. GPU compute partition
and AI model/process/VM services remain absent. Boot is repacked locally from
the exact R66 base; private ramdisk/DTB parts are not uploaded to GitHub.

CI requires SchedTune and frequency boost still enabled, no SCHEDUTIL config,
no schedutil/sugov symbols in System.map, and no schedutil text in Image.
Actual EnergyStep C worker/stop/tunable/table regressions still run.

This is the independent ALICE EnergyStep adaptation for Exynos8895 Linux 4.4.
Removing schedutil does not turn it into Samsung's later EMS governor or
establish physical-device thermal, two-app reclaim or boot stability.
