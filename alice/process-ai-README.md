# ALICE V12R63 – Process Intelligence / Galaxy S8+ Android 16

## Boot and kernel
- Reuse ALICE V12R61 built-in kernel telemetry and root-controlled sysfs VM mode.
- CPU clocks / voltages / governor, GPU DVFS and Samsung DTB remain unchanged.
- MGLRU compiled but OFF by default. MGLRU cannot run on Mali GPU or Samsung VPU.
- The trained neural model must execute in userspace, not inside Linux kernel.

## Newly implemented in Android app
1. Inspect real third-party app PID, starttime, UID, RSS, cumulative CPU ticks,
   nice, and Android oom_score_adj via KernelSU root.
2. Show process ranking and pass bounded observation text to the Qwen3 model.
3. Qwen3 can suggest one PID in machine-parsable text, but can NEVER execute
   a root command: user must approve; code rechecks PID and permissions.
4. Manually lower background app priority to nice +10 only when UID >= 10000
   and oom_score_adj >= 900. This does not kill apps and will not free RAM.
5. User-started foreground monitor scans every 30 seconds. If the SAME
   process uses >=150 CPU ticks and >=96 MiB RSS while cached, apply at most
   one reversible priority change every 120 seconds.
6. User stop / manual rollback restores previous nice values, verifying starttime
   to prevent actions on an unrelated process using a recycled PID.

## Protections and limits
- No kill, signal-stop, freezer, unsafe CPU voltage/frequency, SELinux,
  thermal or MGLRU switch operations.
- Automatic decisions are measured/rule based, not decisions made by a
  trained neural model; Qwen3 outputs proposals which require user approval.
- KernelSU root is still needed to read and adjust other app processes.
- The foreground monitor is OPT-IN and does not launch by default at boot.
- A foreground service consumes energy; throttling apps may delay tasks.
- The V12R61 boot already supplies the required kernel/proc interfaces,
  so no new risky boot image is necessary for process handling.
- Not certified as stable on a physical Exynos 8895 S8+.
