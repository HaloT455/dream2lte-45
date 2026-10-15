# R11: GPIS SurfaceFlinger cpuset and EnergyStep effective targets

## Reproducible defects

The audited One UI configuration exposes `GpisSfCpusetJoin` for a group named
`sf`, but that group is absent. GPIS enable/disable use a relative `cpus`
attribute. A task still in the root cpuset consequently tries to write the
read-only root mask. The kernel correctly rejects this; relaxing root cpuset
semantics or switching SELinux to permissive would not fix the configuration.

The governor resolves discrete hardware OPPs but previously did not include
the Exynos driver's PM QoS floor/cap in its target cache. Different demands
could wake the slow worker for the same QoS-constrained hardware result.

## Boot integration

The existing KernelSU init-RC injection adds a synchronous `post-fs-data`
action, after KSU's existing module setup, bounded by `timeout 8`. It creates
`/dev/cpuset/sf` with the root memory-node mask and initial CPUs `0-7`, grants
system ownership to that child's control files, and bind mounts a patched
task-profile view. Root, foreground, background and top-app masks are untouched.

Only two actions change: `GpisSfCpusetEnable` and `GpisSfCpusetDisable` use
`WriteFile` with absolute `/dev/cpuset/sf/cpus`, retaining their original
`4-7` / `0-7` values. Absolute actions remain correct whether the target task
has already joined `sf` or still belongs to the root/another group. Merely
changing the relative attribute to `sf/cpus` would be wrong for an SF task
already in `sf`: it can resolve to `sf/sf/cpus`.

The original system partition is not rewritten. The fix requires an exact
audited input SHA-256 and verifies the exact output SHA-256; unknown profiles
are skipped. It preserves the original file's SELinux context, uses no new
policy exception, and leaves original configuration in place on preparation
or bind failure. The full ROM configuration and user logs are not committed.

A bounded `init.svc.surfaceflinger=running` action requests whole-process
membership via the child's `cgroup.procs`, after verifying executable name,
system UID, and the patched profile hash. It also covers service restarts.
There is no resident tuning loop or application-specific kill/affinity rule.

Runtime log: `/data/adb/alice-cpu-compat/status.log`.
To disable for the next boot, create `/data/adb/alice-cpu-compat/disable` and
reboot. A normal reboot into an older boot image removes this transient bind
view; the source system partition is unchanged.

## EnergyStep integration

A read-only Exynos ACME helper exposes the same `apply_pm_qos()` snapshot
already used by the real driver. EnergyStep folds that snapshot into OPP
resolution before committing/queuing work. The actual driver still rechecks
QoS at execution time, including races after resolution. No cpufreq structure
layout, thermal threshold, voltage, clock table or PM QoS callback changes.

Raw utilization alone is no longer a valid cache key: a QoS floor/cap can
change while scheduler utilization is unchanged. Resolving every sampled
demand allows both tightening and release to reach the governor. Identical
effective OPPs still return before the slow worker is queued. Existing
3 ms up / 12 ms down limits remain unchanged.

Actual-C tests cover 100 differing above-cap demands with zero redundant
worker enqueues, identical-utilization cap/floor release, policy-limit
priority, invalid QoS fallback, and static-governor compatibility.

## Preserved behavior and verification limits

MGLRU remains off by default. EnergyStep remains the default; schedutil stays
absent. GPU bias -5, EAS margin 1152, PSI bootstrap/idle accounting, the
bounded optional LMKD module, KSU 32590 and Enforcing remain in place.
R10 DNS/Wi-Fi integration is retained without modification.

Host tests compile the actual linked RC and decode its complete payload;
execute the actual CPU script against synthetic Android fixtures; and verify
the compiled ARM64 Image. These do not prove this OEM init's runtime order,
real mount/SELinux acceptance, GPIS task membership, lower device temperature,
longer battery life, or elimination of application/framework stalls. Device
measurement remains necessary. This is a targeted fix, not a claim that every
observed source of heat or lag is resolved.

Primary references:
- https://docs.kernel.org/admin-guide/cgroup-v1/cpusets.html
- https://source.android.com/docs/core/perf/cgroups
- https://android.googlesource.com/platform/system/core/+/android16-release/libprocessgroup/task_profiles.cpp
- https://android.googlesource.com/platform/system/core/+/android16-release/rootdir/init.rc
