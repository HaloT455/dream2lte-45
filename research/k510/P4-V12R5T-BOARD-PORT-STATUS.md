# K510 P4 — V12R5T (Linux 4.4.302) board port into genuine Linux 5.10.262

## Source integrity and measured FDT facts

Local verified V12R5T original 40MiB BOOT SHA256: `76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823`.

Extracted V12R5T FDT SHA256: `c53ccec95ec4eb428e8aa001060526c24b9a6ba734d678cc65cd579ce1357987` (227,317 bytes, 1,274 nodes, 8,149 properties, 344 compatible properties, **173 distinct compatible strings**). Samsung DTBH v2 has one Exynos8895 entry (hw rev10–255), plus a duplicated DTBH in original BOOT. This repo stores derived board facts, **not** private user BOOT, OEM calibration blobs, or complete Samsung vendor DTS.

Do NOT equate 24 KiB minimal K510 DTBH to the 224 KiB original Samsung DTBH; porting functional dependencies is required, not artificially inflating the blob.

## Completed in P4A (automated, compiler-checked)

| Original measured source | Mapped to Linux 5.10 | Status |
|---|---|---|
| ARM Cortex-A53 + Mongoose cores | `exynos8895.dtsi` v6.13 backport, PSCI | Base present from P1 |
| GIC and timer, 26MHz | Generic GIC and armv8 timer, oscclk=26000000 | P4 clock set |
| 3 physical RAM ranges + 12 carveouts | P1D overlay, conservative `no-map` | Present, runtime unverified |
| Samsung `/uart@10430000` reg 0x100, IRQ385 | Linux `samsung,exynos5433-uart`, exynos4210 fallback, mainline clock IDs 17/16, `uart0_bus` pins | **Enabled** for diagnostic console; physical wiring unverified |
| Power / Vol-down / Vol-up / Bixby | `gpio-keys` with GPIO bank and pinctrl (gpa2-4, gpa0-4, gpa0-3, gpa0-6) | Enabled, hardware unverified |
| UFS `/ufs@0x11120000`, IRQ334 and four MMIO windows | Basic descriptor `samsung,exynos7-ufs` with original MMIO, pinctrl, IRQ | **Explicitly disabled** until UFS PHY / clocks / vendor calibration / power regulator checked |
| Samsung ramoops 0x92000000, 0x8000 | P2G-R1 `PSTORE_RAM` and reserved-memory | Present, never produced boot logs yet |

## NOT ported; no claim that Android / One UI is bootable

1. Samsung UFS PHY programming, calibration tables and regulator power sequence (`samsung,exynos-ufs` downstream binding does NOT directly match upstream 5.10 `samsung,exynos7-ufs`). The enabled Linux driver binary alone is insufficient.
2. Panel, DSI, DECON and advanced DRM display driver. R3 uniLoader donor simplefb/DECON is a diagnostic experiment only; its MMIO write is not verified on SM-G955F.
3. MAX77865 charger/fuelgauge + off-mode charger service, PMIC and Type-C roles.
4. Mali GPU, audio ABOX, camera IS/ISP, modem/RIL, Wi-Fi/BT, fingerprint, sensor hubs, thermal and SMMU domain support.
5. Android 16 binder/ashmem substitutes/SELinux, EROFS/vendor mounts, Android-compatible fstab/ramdisk and system integration. P2G current initramfs only prints a heartbeat.
6. Complete DTBH layout and Samsung BOOT handoff / pre-Linux execution verification. Three generations R1/R2 showed no verified Linux 5.10 startup.
7. The remaining 1,274-node vendor Device Tree must be reconciled node-by-node with the current upstream binding/driver; copying raw vendor phandles from a 4.4 DTB into 5.10 is incorrect.

## Policy for next commits

- Preserve known-good V12R5T BOOT and TWRP.
- Compile-only CI, no new flashed image from P4A until Linux startup evidence.
- UFS must remain status=disabled until **all** PHY, power and clock requirements are implemented and tested; do not write unknown registers.
- Never enable an entire downstream 4.4 DTB under 5.10; hardware side effects can be damaging.
- Reconcile kernel drivers and Android/vendor ABI after proving Linux 5.10 runs.

This is a **real first-stage board-data port**, not a finished Exynos8895 full driver backport or stable Android 16 kernel.
