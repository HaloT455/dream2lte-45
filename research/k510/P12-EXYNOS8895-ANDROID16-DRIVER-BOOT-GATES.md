# K510 P12 — Real driver-port staging toward Android 16 / One UI 8

Status: **Native Linux 5.10 UFS host + Exynos UFS PHY + regulator frameworks compiled**, but Exynos8895 board-power, UFS PHY calibration, Android init and vendor HAL integration remain **incomplete**. THIS IS NOT A FUNCTIONAL UI8 KERNEL OR FLASHABLE BOOT.

## Hardware observations already proven on SM-G955F

- P10 BOOT SHA256: \`050d25691e260fa4e47737b26a2ff564d05d341693dcd44618b0358e79ef089b\`.
- Previous pstore contained corrupted but recognizable P2A PID1 init/heartbeat markers from Linux 5.10. It did NOT show UFS probe, power_supply, screen rendering or Android init.
- P11 BOOT SHA256: \`8b3b6864ef0c1eb9344da3df47421387b1f463dee45f02a0683e15088a4ed881\`. User waited ~2–3 minutes, still saw retained uniLoader screen; TWRP pstore EMPTY afterward. Cannot conclude whether P11 reached PID1.
- TWRP stock 4.4 successfully enumerated UFS and charging, but those are independent vendor drivers. Linux 5.10 P11 still has UFS DT \`status = "disabled"\`.

## P12 changes (exact)

- Enable built-in Linux 5.10.262 driver frameworks: \`CONFIG_PHY_SAMSUNG_UFS=y\`, \`CONFIG_SCSI_UFS_EXYNOS=y\`, \`CONFIG_REGULATOR=y\`, \`CONFIG_GENERIC_PHY=y\`, the underlying UFSHCD and dependencies.
- Compile **actual** \`drivers/phy/samsung/phy-samsung-ufs.o\` and \`drivers/scsi/ufs/ufs-exynos.o\`; verify output ELF/DTS; do not merely assert Kconfig strings.
- Critical **fail-closed** condition: \`/soc@0/ufs@11120000\` remains disabled. Compiling the Exynos7 PHY does not validate Exynos8895-specific calibration, private UNIPRO tuning or supply rails.
- Add *local-only* verified V12R5T \`boot.img\` ramdisk extractor, SHA-256 pinned to original BOOT. The extracted initramfs is not committed/shared to public GitHub, is **not inserted into P12 CI**, and no hybrid Android BOOT is created.

## Actual required V12R5T donor sources and engineering blockers

1. \`drivers/mfd/s2mps17_core.c\`: read/write calls \`exynos_acpm_read_reg()\` and related functions declared by \`<soc/samsung/acpm_mfd.h>\`. A generic Samsung 5.10 \`REGULATOR_S2MPS11\` does **not** imply S2MPS17 support. Migrate ACPM mailbox/IPCs, addressing, IRQ and MFD child enumeration before any regulator writes.
2. \`drivers/regulator/s2mps17.c\`: requires S2MPS17 private headers, IDs, buck/LDO tables, voltage selectors, regulator consumers/supply map. Convert 4.4 API carefully; keep regulator **read-only diagnostics** until safe enable/disable sequencing is verified.
3. \`drivers/scsi/ufs/ufs-exynos.c\`: vendor 4.4 version ~65KB embeds SoC-specific UNIPRO, M-PHY calibration, sysreg, clock and private Samsung APIs. Linux 5.10 generic \`ufs-exynos.c\` is not directly equivalent. Exynos8895-specific variant cannot be claimed by adding just Exynos7-compatible DT \`status=okay\`.
4. PHY: Linux 5.10 \`drivers/phy/samsung/phy-samsung-ufs.c\` matches \`samsung,exynos7-ufs-phy\`, not necessarily Exynos8895 physical PHY sequence. A backport or dedicated variant needs Samsung calibration data and mapped clocks/regulators.
5. \`drivers/mfd/max77865.c\`, \`drivers/battery_v2/max77865_charger.c\`, \`max77865_fuelgauge.c\`: mandatory for charging, fuel gauge and charger-off mode together with Samsung Android LPM/charger userspace; TWRP 4.4 charging is not proof P12 can charge.
6. Android 16 One UI 8 boot also needs **exact working V12R5T Android boot ramdisk**, fstab and mount names, vendor compatibility (RIL, Mali, camera services), mandatory binder and SELinux contexts. Android init cannot find system/vendor until UFS enumeration works.

## Acceptance criteria BEFORE proposing experimental One UI 8 BOOT

- PMIC/ACPM driver compiles against 5.10 with source-level dependency trace and DT supplies.
- UFS driver + PHY + clocks + regulators compiles, probe permitted in a separate, explicitly approved hardware experiment.
- Read-only UFS enumeration on the S8+ is verified (block paths and LUNs; no partition writes). A new read-only first-stage init must report storage.
- Working original V12R5T BOOT ramdisk is extracted locally with \`research/k510/p12-extract-original-ui8-ramdisk.py\`; verified legacy header, compression, expected Android first-stage init and fstab. No private ramdisk in public CI.
- Only then stage an opt-in BOOT with Android init **and** a recovery rollback path; compile success isn't Android boot success. Keep SYSTEM, VENDOR, EFS, CP, RECOVERY and USERDATA unchanged.

## Safety / rollback

Known-good V12R5T 40MiB BOOT SHA-256: \`76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823\`. Preserve TWRP and Download Mode. This P12 CI publishes **config and DTB compile evidence ONLY, not boot.img**. Do not flash P12 DTB by itself.
