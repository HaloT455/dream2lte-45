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

## Current energy-aware-only profile

The S8+ defconfig enables `CONFIG_CPU_FREQ_ENERGY_AWARE_ONLY=y`.
`energy_aware` is the sole compiled and registered CPUFreq governor, including
at startup. Schedutil, the older compatibility energy_step governor,
interactive, ondemand and the performance fallback cannot be selected in this
profile. Scheduler EAS placement remains enabled with WALT utilization.

The Galaxy A53 EGO energy-search and CLKOFF/PWROFF idle-time mechanism is
backported to the S8+ Linux 4.4 interfaces. The governor evaluates explicit DTS frequency/capacity/core-power/cluster-power
states and selects the feasible state with the lowest predicted energy. It
has no proportional utilization-to-frequency target, separate up/down rate
limits, busy-CPU frequency hold, IOWAIT frequency boost or optional power-budget
mode. Its worker only passes the selected state to the sleeping Exynos driver.

A53 uses 9 modeled states from 455 to 1690 MHz; Mongoose M2 uses 13 from 741 to
2314 MHz. Higher firmware OPPs are excluded because this tree has no matching
energy costs for them. This is an intentional reduction from the old 2002/
2704 MHz limits. Core and shared-cluster busy/idle costs come from Samsung DTS;
these are model units, not measured battery watts. The explicit frequency
bindings follow the ordered stock OPPs and capacity ratios in that DTS.

Runtime diagnostics under each policy's `energy_aware/` directory expose
`energy_steps` (full state/power/delta table), `energy_step` (last acknowledged
state), `energy_delta` (last transition's busy-power change), and
`predicted_energy` (latest target cost over a common normalized window), and
`idle_ratios` (observed per-CPU CLKOFF/PWROFF shares).
Policy min/max, thermal caps, native Samsung PM QoS and the voltage driver still
apply. See [the model and verification details](docs/ALICE-S8PLUS-ENERGYAWARE-A53-EGO-ESG.md).

KernelSU manual hooks, LZ4KD and other non-CPUFreq features retain their existing
configuration. A successful build does not establish physical boot stability
or battery savings; those require tests on the S8+.

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
