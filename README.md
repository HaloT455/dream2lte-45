# dream2lte Linux 4.4.302 kernel source

Reconstructed buildable kernel source for the Samsung Galaxy S8+ Exynos
(`dream2lte`, SM-G955F) from the supplied 2026-08-04 boot image.

The tree is based on Linux 4.4.302 for Exynos 8895 and includes the matching
device configuration, DT sources, Samsung drivers and KernelSU manual
hooks. KernelSU is vendored in the tree, so a normal build does not fetch or
modify source code over the network.

## Build

Required host tools include `make`, `bc`, `bison`, `flex`, OpenSSL development
headers and the Arm GNU Toolchain 14.2.Rel1 AArch64 cross compiler.

```sh
export CROSS_COMPILE=/path/to/arm-gnu-toolchain-14.2.rel1/bin/aarch64-none-linux-gnu-
./scripts/build_dream2lte.sh
```

Artifacts are written to `out/arch/arm64/boot/Image` and
`out/arch/arm64/boot/dtb.img` by default. Set `OUT` and `JOBS` to override the
output directory and parallel job count.

The build script sets the metadata recovered from the reference image. Use a
new/empty output directory when producing the reproducible release build.

## Current EAS profile

- WALT-backed EAS with schedutil as the default and only dynamic CPU frequency
  governor; the mandatory performance fallback remains compiled.
- Scheduler HMP and the CPU interactive governor are not compiled.
- Cortex-A53 maximum OPP is 2002 MHz. APOLLO thermal polling releases stale
  cooling states below 71 degrees C, so schedutil can reach that OPP instead
  of remaining stuck at cooling state 3 / 1690 MHz after suspend or a power
  event. Real APOLLO heating still progressively caps A53 from 76 degrees C.
- EAS uses Android's schedtune hint to begin latency-sensitive top-app searches
  from M2, preventing `prefer_idle` from accepting an idle A53 before examining
  the high-capacity cluster. Normal work retains cache affinity, and a neutral
  1:1 capacity margin keeps custom A53 spill thresholds removed. Schedutil
  raises an OPP within 1 ms and waits 20 ms before lowering it, spanning a
  60 Hz frame to prevent mid-frame OPP ping-pong without locking a minimum
  frequency. Deferred
  DVFS requests are serialized so an update cannot be lost while the slow
  cpufreq driver is running. Both policy workers run on CPU0, which Exynos
  hotplug keeps online, so an M2 screen-off transition cannot strand its worker.
- Mongoose M2 maximum OPP is the firmware-backed 2704 MHz step.
- Android LMK is removed and replaced by Simple LMK with a 128 MiB minfree
  threshold, global vmpressure trigger, and a bounded 200 ms victim-release
  timeout. Pressure samples reset between allocator stalls so stale data
  cannot trigger kills while idle. Simple LMK starts only after
  Android configures the legacy `lowmemorykiller.minfree` endpoint, runs at
  normal scheduler priority, serializes reclaim requests, and falls back to
  the regular OOM killer only if its worker cannot make progress.
- Hard- and soft-lockup detectors, pstore and the Exynos watchdog stay enabled,
  but transient lockup reports no longer deliberately panic and reboot five
  seconds later. Genuine panics still retain the existing five-second reboot
  timeout and diagnostic storage.
- The MAX77865 wired-charger path drains simultaneous fuel-gauge and CHGIN
  interrupts instead of leaving CHGIN masked. Its stability sampler is bounded
  to five seconds, stale QC work is ignored after a cable state change, and the
  battery-presence interrupt passes an initialized value. AFC/QC voltages and
  charging-current limits remain the Samsung defaults.
- HaloT455 KernelSU 32590 is functional through manual security hooks plus the
  legacy-safe `execve/faccessat/stat/reboot` integration used by dream2lte.
  The bundled trust pin matches Manager 32596 supplied for this build. Kprobes,
  syscall-table tampering, ARM64 branch rewriting, the obsolete direct
  `setresuid` hook and the downstream GID 3009 patch remain disabled.
- The permissive build pins the SELinux runtime state to permissive, including
  when Android init later requests enforcing mode.
- GPU frequency limits and CPU voltage tables are unchanged. M2 thermal
  control remains stock; the A53 APOLLO cooling map is aligned with the
  expanded OPP table and retains hard throttling at high temperature.
- ABOX SRAM IPC uses the required I/O-memory copy helpers.

To create a flashable image while preserving a known-good boot image ramdisk
and footer:

```sh
./scripts/repack_boot_v0.py \
  --base /path/to/known-good.img \
  --kernel out/arch/arm64/boot/Image \
  --dt out/arch/arm64/boot/dtb.img \
  --output dream2lte-eas.img
```

See [docs/REFERENCE_IMAGE.md](docs/REFERENCE_IMAGE.md) for provenance,
reconstruction notes and verification results.

## Important

This repository contains reconstructed source, not a claim that the original
private build tree can be recovered byte-for-byte from a compiled image. The
configuration, version metadata, DT target, features and produced artifact
sizes were independently checked against the supplied image.

Linux kernel code remains licensed under GPL-2.0; see `COPYING`. Vendored
components retain their own license notices.
