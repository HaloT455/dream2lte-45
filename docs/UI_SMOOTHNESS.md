# Kernel UI1 candidate, based on stable 6ede20ab

The user reports that the suspend/reboot fixes are stable and battery behavior
is acceptable. Preserve that baseline. This is a candidate optimization, not
evidence that the current build drops frames because of schedutil.

## 1. Deferred frequency work

The existing schedutil slow path sets `work_in_progress` but never reads it.
Every accepted frequency change therefore attempts to queue IRQ work, even
when the kthread work is already pending. Both queues suppress duplicate
entries, but the extra queue attempts and potentially redundant IRQ callbacks
are unnecessary.

Coalesce requests while work is pending, keeping the newest target. The worker
copies that target and clears the pending flag in one short `update_lock`
critical section, before entering the sleeping cpufreq driver. A request
arriving after this snapshot queues another pass. The single-CPU slow path also
takes the lock; the shared-policy path already did so.

This follows the deferred-work pattern in
[Linux v4.19 schedutil](https://github.com/torvalds/linux/blob/v4.19/kernel/sched/cpufreq_schedutil.c)
and [Android common schedutil](https://android.googlesource.com/kernel/common/+/refs/heads/android12-5.10/kernel/sched/cpufreq_schedutil.c).
Only queue handling is adapted, not the upstream governor or scheduler wholesale.

Unchanged: 2.5 ms up / 8 ms down limits, WALT/EAS placement, touch-boost values,
CPU/GPU OPPs, voltage tables, thermal policy, SimpleLMK, watchdog, reboot reasons,
and the schedutil worker's per-policy CPU affinity. There is no new wakelock,
polling daemon, boost timer, or suspend fallback.

## Host checks

```sh
python3 scripts/test_schedutil_work.py
sh -n scripts/collect_ui_perf.sh
git diff --check
```

The host test extracts the actual changed C functions, compiles them with mocked
queues/driver/locks and UBSan, then checks pending-request coalescing, updates
before/during/after the driver, unchanged-frequency handling, up/down rate
limits and the stubbed fast path. The old implementation should fail the
coalescing assertion with `--ref 6ede20ab`. It does not model the whole scheduler,
real SMP memory ordering, CPU hotplug or suspend. A full ARM64 build and device
testing are still required before a release.

Checks completed for this change:

- Host C regression test with UBSan: passes. Baseline `6ede20ab` fails the
  expected redundant-IRQ-attempt assertion.
- `checkpatch --strict` on the kernel patch: zero errors, warnings or checks.
- Shell syntax and invalid-input handling: pass; the collector refuses to run
  when Android's `dumpsys` is unavailable.
- Defconfig generation succeeds. Differences from the enforcing CI artifact
  are only the workflow's SELinux variant options and release string.
- No modifications to the stable memory, watchdog, reboot or thermal files.
- Full ARM64 compilation and on-device capture: not performed for this change.

## Measure before changing performance policy

Use the same app, gesture, brightness, battery state and similar starting
temperature for baseline and candidate. Measure on battery without holding the
earlier `alice_no_suspend` diagnostic wakelock. Do not disable thermal limits.

The read-only capture script prints two snapshots without resetting gfxinfo,
dropping caches or writing any kernel controls. It is not a background logger.
For example, from a computer with ADB:

```sh
adb push scripts/collect_ui_perf.sh /data/local/tmp/collect_ui_perf.sh
adb shell su -c 'sh /data/local/tmp/collect_ui_perf.sh com.android.systemui 20' > ui-perf.txt
```

Repeat the affected gesture during the 20-second capture. For app scrolling,
replace `com.android.systemui` with that app's package. SystemUI, Samsung
Launcher and Launcher3 are also queried for recents/transition animation data;
missing launcher packages can be ignored. A device-side root
terminal can run the same script and redirect to `/sdcard/Download/ui-perf.txt`
to capture with USB disconnected. Review the output before sharing; gfxinfo
can contain activity/window names, though the script collects neither logcat
nor app content.

Compare frame timestamps present only in the second snapshot; gfxinfo retains
history, so cumulative jank totals alone are not a valid A/B measurement. Its
HWUI frames do not cover every SurfaceFlinger, video, game or Vulkan workload.
Frequency residency and VM counters are coarse clues, not proof of a bottleneck.
If they are inconclusive, a narrowly scoped scheduling/rendering trace is the
next step. Do not declare stock-equivalent smoothness without device results.

## 2. Native CPU-cgroup hints (no system/ramdisk edits)

The uploaded `ui-perf.txt` records about 24 seconds of activity on Android 16:
306 additional launcher frames, of which 46 were janky (~15%). Launcher GPU
histogram P95 is about 13 ms while whole-frame P95 is about 77 ms. Temperature
samples were below the 65 C threshold. These observations justify looking at
CPU-side scheduling/dispatch, but do NOT establish it as the only cause: Binder,
locks, application work, reclaim and unmeasured I/O can also delay these frames.

The supplied `ui-policy.txt` declares existing CPU cgroups under `/dev/cpuctl`:
`top-app`, `foreground`, and `foreground_window`. No SchedTune controller is
declared or mounted in the captured output. The uclamp attributes are not a
working replacement in this 4.4 tree, and min/max declarations alone are not
evidence of actual uclamp writes. Live per-thread CPU cgroup membership still
needs confirmation; the enhanced collector reads it for the main and render
threads. There are no process IDs, package names or thread-name matches in the
kernel policy itself.

`CONFIG_SCHED_CPU_UI_HINTS` is enabled only in the dream2lte defconfig. It uses
the ROM's existing CPU group assignments to supply these initial test values:

| Root-level CPU group | SPC boost | Prefer idle CPU |
| --- | ---: | ---: |
| top-app (and descendants) | 10 | 1 |
| foreground (and descendants) | 5 | 0 |
| foreground_window (and descendants) | 5 | 0 |
| root, background, all other groups | 0 | 0 |

SPC adds a percentage of the unused utilization range, not a fixed percentage
of clock speed. These are experimental policy values, not measured optimums
and not a uclamp backport. Task utilization, CPU utilization, idle placement,
and EAS energy/performance thresholds all receive the same policy. Existing
CPU affinities, quotas, maximum frequencies and thermal controls still apply.

Implementation safeguards:

- Match exact root-level names once at group creation. Children inherit their
  parent's immutable identity; an unrelated nested `top-app` is not special.
  As with a configured group property, a live rename retains the original
  policy. Another group cannot replace an occupied registry slot. Android's
  fixed init-created group names are the supported layout; arbitrary dynamic
  renaming/replacement is not a supported policy-discovery mechanism.
- Query the three groups' existing CFS `h_nr_running` counters. No new task
  counters, enqueue/dequeue/exit hooks, timers, workers or extra runqueue locks.
  Sleeping tasks contribute no hint; bandwidth-throttled groups are skipped.
  Throttled descendants are already excluded from their parent's CFS count.
  Remote-CPU reads are advisory snapshots, not globally atomic measurements.
- Publish group pointers under cgroup_mutex using RCU; remove them at
  css_released, before the cgroup core's grace period and css_free.
- A mounted SchedTune controller disables the fallback, including when native
  boost is zero or negative. No combining/doubling of native and fallback boost.
- `kernel.sched_cpu_ui_hints=0` disables the policy immediately for subsequent
  scheduler queries. It does not reset CFS accounting or force an immediate
  hardware frequency transition. Existing Schedutil rate limits still apply.
- Read-only `cpu.ui_hint_boost` and `cpu.ui_hint_prefer_idle` show the effective
  fallback for each group (zero when fallback is disabled). No fake uclamp files.

No changes to system/vendor JSON, init scripts, ramdisk, SimpleLMK, recovery,
suspend, watchdog, CPU/GPU voltage or OPP tables, thermal thresholds, affinity,
cpusets, I/O, swap/ZRAM, or SELinux behavior within each original variant.

Additional host check:

```sh
python3 scripts/test_cpu_ui_hints.py
```

This compiles the actual implementation and changed SchedTune entry points
with UBSan, including CFS bandwidth enabled/disabled and feature-disabled
stubs. It tests group identities, inherited policy, advisory runnable counts,
throttling, registry release/recreation, initialization, native SchedTune
precedence including negative boost, and EAS threshold routing. Mocks validate
read-side RCU boundaries; they do not simulate true concurrency or prove CFS
accounting on hardware. Full ARM64 Enforcing/Permissive builds run in CI.

Optional device A/B switch, no module or reboot required (Windows CMD):

```bat
adb shell "su -c 'cat /dev/cpuctl/top-app/cpu.ui_hint_boost /dev/cpuctl/top-app/cpu.ui_hint_prefer_idle'"
adb shell "su -c 'echo 0 > /proc/sys/kernel/sched_cpu_ui_hints'"
adb shell "su -c 'echo 1 > /proc/sys/kernel/sched_cpu_ui_hints'"
```

Expected values for an active fallback are `10` and `1`. If zero or missing,
inspect mounts, kernel version and actual task membership before tuning more.
The switch controls only CPU-group hints; comparison to the original stable
boot is needed to also isolate the deferred-work change. Test unplugged idle
and repeated sleep/wake, recovery reboot, thermals/battery, and the same UI
gesture before adopting the candidate. Keep the known-good boot available.

Design references: [AOSP capacity-related jank](https://source.android.com/docs/core/tests/debug/jank_capacity)
and [SchedTune SPC documentation](https://android.googlesource.com/kernel/msm/+/android-msm-marlin-3.18-nougat-dr1/Documentation/scheduler/sched-tune.txt).
