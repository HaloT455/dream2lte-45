# dream2lte Linux 4.4.302 kernel source

Reconstructed buildable kernel source for the Samsung Galaxy S8+ Exynos
(`dream2lte`, SM-G955F) from the supplied 2026-08-04 boot image.

The tree is based on Linux 4.4.302 for Exynos 8895 and includes the matching
device configuration, DT sources, Samsung drivers and KernelSU-Next manual
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
- Cortex-A53 maximum OPP is 2002 MHz. Below 65 degrees C the APOLLO thermal
  zone releases stale cooling limits so schedutil retains the complete OPP
  range. At 65 degrees C and above it applies progressively stronger caps.
- EAS begins wakeup placement near the task's previous CPU to preserve cache
  and avoid waking Mongoose M2 for every boosted UI frame. It still scans both
  clusters and can select M2 when utilization requires it. There is no fixed
  85% A53 gate; schedutil uses a 2.5 ms up delay and 8 ms down delay for short
  responsive bursts without retaining a stale overclocked OPP.
- Mongoose M2 maximum OPP is the firmware-backed 2704 MHz step.
- Complete SimpleLMK is enabled with global and memcg vmpressure triggers,
  bounded victim waits and the original OOM fallback when reclaim cannot run.
  Rescue2 tracks SimpleLMK victims separately from genuine OOM victims so the
  OOM counter cannot underflow and deadlock the suspend freezer. Disabling the
  OOM killer is also bounded to five seconds so a stuck victim aborts suspend
  instead of allowing the hardware watchdog to reset the phone.
- KernelSU 32590 uses manual Samsung 4.4 security hooks; automated LSM hook
  insertion, kprobes, syscall-table tampering, and hosts redirect are disabled.
- The permissive build pins the SELinux runtime state to permissive, including
  when Android init later requests enforcing mode.
- M2 retains the complete 741MHz..2.704GHz schedutil range while cool. Its
  power allocator now starts budgeting at 55 degrees C and targets 70 degrees
  C, reducing surface heat without removing the top OPP from schedutil.
  GPU limits, CPU voltage tables, battery charging protection, and CPU hot
  safety trips remain in place.
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
