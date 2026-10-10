# P5 — V12R5T Linux 4.4.302 -> K510 Linux 5.10.262 driver migration

## Source pinned and safety

- Exact V12R5T donor **source** branch `agent/v12r5t-mglru-aging-stability`, Git commit `3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3`. No guessing firmware blobs or third-party variants.
- Target upstream kernel genuine Linux **5.10.262** fetched in CI by `research/k510/bootstrap.sh`. This is a DIFFERENT major kernel with different driver/ABI/Kconfig APIs.
- The existing V12R5T Linux 4.4.302 device is stable. No P5 script writes to BOOT, RECOVERY, SYSTEM, VENDOR, EFS, or modem.
- Do **NOT** present this as a complete port, Android 16 stable boot, or evidence that all vendor modules link into 5.10.

## Port status

| Subsystem from V12R5T | Linux 5.10 strategy | Current status |
|---|---|---|
| CPU/GIC/PSCI/clock/pinctrl/RAM/ramoops | Existing P1/P4 board DTS and backports | Compiles; no hardware boot proof |
| Debug UART and four keys | P4 mainline Samsung serial and GPIO-keys with mapped pins | Compiles; actual UART console not tested |
| V12R5T Android Binder devices | P5 `ANDROID_BINDER_IPC`, `ANDROID_BINDER_DEVICES=binder,hwbinder,vndbinder` | Native Linux 5.10 build integration |
| V12R5T EROFS/F2FS userspace filesystems | P5 Linux 5.10 EROFS, F2FS and xattr/security | Native kernel integration; vendor mount path untested |
| SELinux, cgroups, namespaces, dm-crypt and dm-verity | P5 upstream Linux 5.10 config and dependency audit | Kernel integration, Android 16 policy ABI untested |
| UFS Exynos `drivers/scsi/ufs/ufs-exynos.c` | 5.10 already has same-name driver but **different API** and Exynos7 bindings | Driver compiled by P4; UFS DT node disabled pending 8895 PHY/calibration |
| MAX77865 charger + fuel gauge | `drivers/battery_v2/max77865_{charger,fuelgauge}.c`, `drivers/mfd/max77865.c` | **Not ported to Linux 5.10** |
| S2MPS17 regulator/PMIC | `drivers/mfd/s2mps17_core.c`, `drivers/regulator/s2mps17.c` | **Not ported**; DO NOT substitute S2MPS11 as exact-compatible |
| DECON, DSIM and Galaxy S8+ AMOLED panel | `drivers/video/fbdev/exynos/dpu/*` + panel DTS | **Not ported**; R3 uniLoader DECON/simplefb only probes stage |
| Mali Bifrost r19p0 / ION / DMA-BUF | `drivers/gpu/arm/tMIx/` and dependencies | **Not ported**; proprietary vendor/HAL ABI needs review |
| FIMC-IS2 camera/ISP | `drivers/media/platform/exynos/fimc-is2/` | **Not ported**; vendor firmware, SMMU and memory dependencies |
| Bluetooth/Wi-Fi/NFC, audio and modem | Donor device-specific source, firmware and service ABI | **Not ported** |
| Android ramdisk, charger OFF, vendor/system compatibility | Original V12R5T ramdisk/Android 16 vendor integration | **Not started**: existing K510 initramfs only prints heartbeat |

## Mechanical source analysis

`research/k510/p5-audit-v12r5t-drivers.py` performs a reproducible file-level inventory against pinned V12R5T commit and genuine 5.10.262 tree. Outputs a CSV with per-file donor Git blob SHA and whether the target path exists. **Same path does not mean the file is binary/API compatible.** Missing paths identify candidate source migration; each still needs a separate Kbuild patch and a hardware binding proof.

The P5 CI artifact includes `V12R5T-DRIVER-MIGRATION.csv`, `V12R5T-MIGRATION-SUMMARY.json`, the merged 5.10 `.config`, and compiled DTB if all tests pass. It intentionally includes **no flashable BOOT**.

## Next real engineering milestones

1. Confirm first Linux 5.10 kernel instruction on S8+ using verifiable early console / stage probe. Empty TWRP pstore in R1/R2 cannot locate boot hang.
2. Port Exynos8895 UFS PHY and controller calibration, clock/regulator references; validate read-only detection and block access before writing storage. Keep `ufs@11120000 status=disabled` until validated.
3. Port S2MPS17/Max77865 platform, power and fuel-gauge drivers with exact V12R5T register map, adapt to 5.10 regulator/power_supply APIs.
4. Adapt Samsung DECON/DSIM/panel driver to DRM atomic kernel interfaces, and Mali r19p0 / ION allocations to DMA-BUF/SMMU.
5. Port FIMC-IS2, modem, audio, radios, sensors and thermal; solve API and firmware compatibility.
6. Only then rebuild the Android 16 boot ramdisk and validate One UI 8 vendor ABI, init services, SELinux and offline charger.

Passing `make Image` alone does not prove stages 1–6. This is incremental kernel engineering, not a single one-click bulk-copy operation.
