# K510 P18 — ACPM/Speedy Power Dependency + Exynos8895 UFS PHY Calibration Audit

Base: P17 \`vmlinux\` final link PASS, seven ACPM/S2MPS17 objects. P18 is a **nonflashable source/Device Tree investigation** toward Android 16 One UI 8, not a working replacement kernel.

## P18 concrete implementation

1. Pin working V12R5T donor commit \`3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3\` for exactly reproducible vendor source data.
2. Parse the original Exynos8895 SoC and Dream2LTE board Device Trees to inventory:
   - Samsung ACPM AP2APM mailbox/SRAM, IRQ and firmware initdata base.
   - S2MPS17 MFD regulator dependence on ACPM channel 2 and **Samsung Speedy** interface.
   - UFS host register windows, clock-names, GPIO-controlled VCC, PHY/TCXO blocks.
   - PHY/UniPro register tuning tables by actual names, counts and SHA-256.
3. Compare vendor \`samsung,exynos-ufs\` with native Linux 5.10 \`samsung,exynos7-ufs\` bindings. Explicitly prevent unsupported equivalence claims.
4. Verify generic Linux 5.10 PHY and UFS host objects compile; build Exynos8895 research DTB and reject any \`status=okay\` UFS node.
5. Import the **unaltered** vendor \`ufs-exynos.c\` and \`ufs-exynos.h\` to a quarantined temporary Kbuild path and attempt genuine compilation against 5.10 headers; collect precise missing APIs and headers. On an API failure CI may pass its **audit** job, but report \`VENDOR_4_4_TO_5_10_API_PORT_BLOCKED\`; never claim UFS migration PASS.

## Explicit unresolved gates

- ACPM firmware binary, mailbox handshake, SRAM mapping and fail-safe timeouts not hardware verified.
- Samsung Speedy transport and S2MPS17 register/rail sequencing require correct 5.10 implementation; a generic \`REGULATOR_S2MPS11\` is not equivalent.
- Exynos8895 M-PHY/UniPro variants require calibrated register writes and clocks proven against vendor original.
- UFS enumeration, power_supply, display, Android \`/init\` and One UI 8 runtime are NOT tested.
- **No flashable BOOT or kernel Image**, no experimental hardware probe, and no change to existing V12R5T, modem, recovery, EFS, system or userdata.

## Acceptance

A P18 audit PASS means the hardware inventory and genuine API diagnostic ran correctly. Only verified API compatibility, correct power/PHY sequencing, full final kernel link and controlled read-only UFS hardware enumeration in a **future separately approved experiment** could warrant a boot-image test.

Artifact \`ALICE-K510-P18-ACPM-UFS-DEPENDENCIES-NO-FLASH\`: YAML/report, JSON calibration counts and hashes, original source checksums, actual compiler logs and no boot binaries. Do not flash these diagnostics.
