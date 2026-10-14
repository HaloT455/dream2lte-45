# R8: MGLRU OFF, native EAS plus EnergyStep, PSI idle shutoff

The user selected their V12R5T boot as the packaging base and requested
MGLRU OFF by default, PSI/LMKD improvements, no schedutil, and load-dependent
performance/battery balance. The supplied image has PSI/EAS enabled and uses
schedutil; its ramdisk and DTB will be retained for the new image. Packaging
and hashes are verified privately rather than uploading that boot to GitHub.

## CPU policy

Energy-aware scheduling selects the CPU on which a task runs. EnergyStep
selects a hardware frequency from scheduler utilization for the shared CPU
cluster. Keep those two functions connected; no governor named energy_aware
is invented, and schedutil stays absent from source, config and linked Image.
The existing Exynos capacity/energy tables and native SchedTune are retained.

R7 used 12.5% headroom for DVFS while task placement predicted 25%. R8 uses
one capacity_margin for both and defaults it to 1152/1024 (12.5%). EnergyStep
reads that shared value. It still raises frequency for actual utilization,
honors min/max and thermal/QoS bounds, maps to actual hardware OPPs, and
retains 3ms up/12ms down hysteresis. Idle I/O boost expires as fixed in R7.
This is a tunable performance/energy tradeoff, not a measured battery claim.

## PSI

- Restore the upstream workqueue last-function identity interface and prevent
  the PSI worker's own sleep from restarting its averaging clock.
- Preserve sub-tick stall totals/trigger activity, but do not mark sub-tick
  nonidle execution alone as a reason to keep averaging scheduled. Otherwise
  the earlier short-sample accounting fix makes PSI's own work self-sustain.
- Advance monitor and average deadlines during the idle polling grace period.
  An overdue polling deadline previously caused work to requeue every tick
  without advancing the deadline if no nonidle sample was collected.

References for worker identity/idle shutoff and monitor windows:
https://kernel.googlesource.com/pub/scm/linux/kernel/git/stable/linux-stable.git/+/refs/tags/v5.4.201/kernel/workqueue.c
https://docs.kernel.org/accounting/psi.html

The new C test exercises real collector, task-change and clock-worker code,
including idle shutdown, retained short stalls, real-trigger wakeup, polling
grace and no every-tick deadline loop. Existing PSI ABI/nesting checks remain.

## GPU load hook and APK slider

The active Mali b_r19p0 governor has a root-writable gpu_boost attribute under
/sys/kernel/gpu, range -10..20, default -5. It scales the load used for the
frequency decision, preserving measured utilization for telemetry/IPA.
Negative bias fades above 80% measured utilization and is zero at 95% and
above. Sustained saturation can therefore still request the native high OPPs.
The driver frequency table, min/max/QoS and thermal controls remain intact.
The requested clock is captured under the DVFS lock before reporting to IPA.

Compute-only job mix previously forced the maximum request even at low total
GPU utilization. Keep that CL boost only at >=95% total measured utilization.
The manual APK exposes the slider and reads/verifies the kernel setting. It
does not persist it or apply it during startup; reboot returns to default -5.
A -5 load bias is not a claim of 5% lower GPU clock or 5% battery saving.
No GPU clock-limit unlock is added to this performance/battery balance build.

## LMKD

LMKD belongs to the ROM's userspace. Kernel boot replacement supplies PSI
accounting/monitor ABI; it does not itself rewrite LMKD properties.

A companion KernelSU module runs once after completed boot. It only invokes
the existing verified low-swap helper when the effective Samsung threshold
exceeds 30%. That helper requires the exact previously analyzed daemon hash,
a single 3–4GB zRAM swap device and adequate available RAM, normalizes the
swap reference, verifies the effective setting, and restores failed changes.
It retains a supported explicit override. Healthy or unrecognized setups
are left alone. No persistent loop, LMKD replacement, OOM-score protection,
thermal override or forced app retention is added. Uninstall restores the
RAM-only properties, and reboot already discards those properties.

The module must be installed in KernelSU for that userspace correction to
apply. status.log reports applied/skipped/failed; skip is not claimed as a
successful LMKD change. The primary-source Android 16 LMKD reference is:
https://android.googlesource.com/platform/system/memory/lmkd/+/refs/heads/android16-release/README.md

Physical boot, Home/SystemUI responsiveness, temperatures, battery discharge,
and actual LMKD module compatibility remain unverified until run on device.
