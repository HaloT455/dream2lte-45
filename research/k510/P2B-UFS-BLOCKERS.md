# P2B — UFS bring-up blockers (SM-G955F / Exynos8895)

Status: **RESEARCH ONLY — NOT IMPLEMENTED**. The P2A minimal initramfs is intentionally independent of UFS.

## Ground truth

- Read-only device inventory on 2026-10-10: UFS appears at `/ufs@0x11120000` and `/ufs@0x11120000/ufs-phy`. BOOT is `/dev/block/sda7` on the known-good 4.4 kernel.
- Samsung 4.4 donor: `arch/arm64/boot/dts/exynos/exynos8895.dtsi` around line 879 includes:
  - HCI standard: **0x11120000 / 0x200 bytes**
  - Vendor block: **0x11121100 / 0x200**
  - UniPro: **0x11110000 / 0x8000**
  - UFS protector: **0x11130000 / 0x100**
  - PHY: **0x11124000 / 0x800**
  - PHY sys control at 0x16480724
  - IRQ 334 (downstream interrupt cells; must convert to 5.10 binding safely)
  - clocks `GATE_UFS_EMBD`, `UFS_EMBD`, PHY and pinctrl states, vcc supply
  - many Exynos8895-specific PMD, PWM and HS calibration register tables.

## Missing in the P1 / P2 5.10 device tree

Linux v6.13's **minimal** Exynos8895 SoC DTS imported during P1 has clocks and pinctrl but does **not** define the UFS controller or its PHY; this must be ported.
Linux 5.10 includes a Samsung Exynos UFS host driver for other SoC variants, but **controller register compatibility, PHY calibration tables, clocks and PMIC must be audited**. Do not bind Exynos8895 to a different SoC string to obtain a compilation-only "success".

## Next code requirements

1. Implement Exynos8895 UFS/controller bindings in the 5.10 DT using actual named ranges, clocks, resets, and PMU phandles.
2. Adapt the PHY driver using Samsung downstream *register-programming and timing data* with safe clocks and regulator sequencing.
3. Ensure the 5.10 regulator/PMIC path supplies PHY and UFS rails; do not invent regulators.
4. Compile a driver-specific boot profile separately from the initramfs-only image, then inspect earlyboot/pstore traces.
5. Only after successful Linux block-device enumeration consider Android filesystem access. **Never mount userdata read/write as an initial test.**

The first P2 objective is to reach an initramfs marker without touching UFS or user data; UFS bring-up follows.
