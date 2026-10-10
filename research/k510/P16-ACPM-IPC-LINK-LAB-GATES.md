# K510 P16 — ACPM IPC + S2MPS17 compatibility and cross-object link evidence

**Scope:** Linux 5.10.262 build laboratory ONLY, sourced from pinned working V12R5T/Exynos8895 kernel revision \`3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3\`.

## Changes from verified P15

- P15 confirmed C compilation of four separate donor \`.o\` files: \`acpm_mfd.o\`, \`s2mps17_core.o\`, \`s2mps17_irq.o\` and \`s2mps17.o\`.
- P16 also stages the *real Samsung sources* \`acpm.c\`, \`acpm_ipc.c\`, their private headers, firmware-*layout* headers and CAL \`fvmap.h\` in disposable Linux 5.10 CI only.
- Add explicit temporary Kbuild rules for both additional ACPM objects; retain P14 and P15 compatibility changes.
- Compile all six objects with the donor ACPM C definition and log per-object compiler findings.
- Only when **all six C objects pass**, run \`aarch64-linux-gnu-ld -r\` and verify that IPC/MFD/PMIC cross-object definitions are present; publish unresolved external symbols via \`aarch64-linux-gnu-nm -u\`.

## Strict qualification

\`ld -r\` makes a *relocatable aggregate object*, NOT a final \`vmlinux\` ELF. It does not prove that all core kernel symbols and Samsung-specific APIs are implemented. It neither loads ACPM firmware nor requests power/clock/UFS resources. \`CONFIG_EXYNOS_ACPM\` is forced during **per-object compilation only** and is not enabled for a runnable image. No Exynos8895 DT power/PMIC/UFS nodes are turned on.

**No flashable \`boot.img\` is generated.** Hardware probe, Samsung Speedy I2C, ACPM IPC ABI/failure handling, rail voltage ownership, PHY/UniPro calibration, UFS enumeration, Android 16 init/ramdisk and display are still separate runtime gates.

## Acceptance

1. No Kbuild harness errors; compiler errors must be surfaced accurately.
2. All six donor files compile; artifact matrix shows each real result.
3. The cross-object \`ld -r\` proof and symbol manifest are present before declaring P16 linkage-lab PASS.
4. Only a subsequent explicitly approved laboratory kernel can test actual AC(P)M and UFS hardware: preserve V12R5T BOOT, TWRP/Download Mode, and user partitions.
