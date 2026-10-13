# V12R69 R5: LRU controls and EnergyStep

The user reports that R4 boots but two concurrent apps still freeze with
MGLRU ON. The supplied log also shows MGLRU OFF with CPU clusters at their
allowed ceilings and SoC readings 69/71 C; one snapshot cannot identify the
cause of the heat.

R5 removes Qwen inference, downloads/chat/voice, process-management services,
adaptive VM modes and the GPU 15/5 compute reservation from the shipped
configuration. The ALICE kernel bridge now exposes only read-only counters.
Native Mali and Exynos VPU drivers remain available to the ROM. MGLRU remains
compiled and user-controllable, with default OFF. Page-table aging and scan
around remain opt-in. No app service or boot task enables it automatically.

EnergyStep retains WALT/PELT, IOWAIT boost, 112.5% utilization headroom and
3/12 ms directional rate limits. It now selects the minimum sufficient
hardware frequency instead of rounding through eight synthetic buckets first.
Exynos uses legacy `.target`; core `resolve_freq()` alone does not quantize
that driver's requests. R5 explicitly uses its cpufreq table, avoiding worker
wakeups for raw targets that map to the same hardware step. Unsampled shared
CPUs are ignored until capacity is populated, rather than creating fake
deadline load or erasing a sibling's valid load. Actual deadline demand obeys
the current policy ceiling. Cached rate restoration uses explicit u64 casts
consistently; this is portability cleanup, not a demonstrated ARM64 bug.

R4's queue-outside-policy-lock and synchronized worker-stop fixes are retained.
Host regressions compile the actual governor and cpufreq-table C, exercise
policy ceilings and unsampled/stale CPUs, and run the shipped LRU shell helper
against mock sysfs. CI builds both the ARM64 kernel/DTB and the lean signed APK.

These changes remove unnecessary components and demonstrable target rounding.
They do not establish that physical two-app MGLRU reclaim or heat is fixed.
Boot packaging must use the user's exact working R66 base locally, preserving
its ramdisk, DTB, addresses and footer; private boot parts are not uploaded.
