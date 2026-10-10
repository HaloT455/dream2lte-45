# P15 — S2MPS17 Linux 5.10 compatibility bridge (compile-only)

## Baseline evidence

P14 [run 38039790549](https://github.com/HaloT455/dream2lte-45/actions/runs/38039790549) completed a reliable Linux 5.10 compile inventory:
- \`acpm_mfd.o\`: C compilation passed
- \`s2mps17_irq.o\`: C compilation passed
- \`s2mps17_core.o\`: blocked by old \`i2c_new_dummy\` and missing Samsung \`I2C_CLIENT_SPEEDY\`
- \`s2mps17.o\`: blocked by missing \`linux/exynos-ss.h\`

## P15 changes, only in the ephemeral downloaded CI Linux source tree

1. Convert Samsung \`i2c_new_dummy\` to 5.10 \`i2c_new_dummy_device\`. New API returns \`ERR_PTR\`; validate every secondary client and unwind on error.
2. Preserve the Samsung Speedy flag only when it actually exists. Otherwise return \`-EOPNOTSUPP\` on the Speedy-requested path; NEVER define \`I2C_CLIENT_SPEEDY\` to zero or silently pretend speed support exists.
3. Copy \`include/linux/exynos-ss.h\` byte-for-byte from pinned working V12R5T donor commit \`3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3\` to compile legacy regulator driver; Exynos Snapshot runtime is NOT ported.
4. Run the P14 truthful Kbuild gate again and report newly uncovered compiler errors.

## Remaining safety gates

Even a green isolated compile does not mean linked ACPM IPC, safe S2MPS17 regulator control, valid power sequence, correct Exynos8895 UFS calibration, Android 16 ramdisk integration, or working NPU. No DT enabling, no BOOT image, no hardware flash from this branch. Do not merge the compatibility probe directly into a production kernel without reviewing lifecycle and device-tree dependencies.
