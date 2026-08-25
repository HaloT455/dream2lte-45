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
- Cortex-A53 maximum OPP is 2002 MHz.
- EAS starts normal work on the efficient A53 cluster, while boosted or
  latency-sensitive work may start directly on Mongoose M2. There is no fixed
  85% A53 gate; schedutil selects frequency from utilization with a 1 ms up
  delay and 20 ms down delay.
- Mongoose M2 maximum OPP is the firmware-backed 2704 MHz step.
- The Samsung kernel low-memory killer is enabled with automatic oom_adj
  conversion so the ROM's lmkd path keeps GID 3009 and boots normally.
- KernelSU 32594 uses manual Samsung 4.4 security hooks; automated LSM hook
  insertion, kprobes, syscall-table tampering, and hosts redirect are disabled.
- GPU frequency limits, CPU voltage tables and thermal limits are unchanged.
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
