# Alice K510 P1 — Exynos8895 Platform Port

**Device:** Galaxy S8+ / SM-G955F / Exynos8895 (dream2lte), hardware rev05 measured by running Android.
**Kernel:** real upstream Linux 5.10.262 fetched from gregkh/linux in CI; original 4.4 repository tree is used only as a workflow host and driver-reference donor.

## Deliverables

| Port layer | Source | CI workflow | Gate |
| --- | --- | --- | --- |
| P1A: Exynos8895 DTS, pinctrl DTS, clock binding IDs, dream2lte skeleton | upstream v6.13 | `k510-p1a-dtb.yml` | DTB compiles |
| P1B: Exynos8895 8-bank pinctrl data + OF match integrated into the **5.10 framework** | upstream v6.13 | `k510-p1b-pinctrl.yml` | Full ARM64 Image compiles |
| P1C: Exynos8895 clock tables + preliminary 5.10 CCF compatibility adapter | upstream v6.13 | `k510-p1c-clock.yml` | Full ARM64 Image compiles |

All compilation steps use a fresh, independently fetched Linux **v5.10.262** tree. The root repository Makefile is still version 4.4, and **must never be renamed to pretend that it is 5.10**.

## Exynos8895 sources

- Samsung downstream 4.4 board source (in this repo): `arch/arm64/boot/dts/exynos/exynos8895-dream2lte_eur_open_09.dts`, `exynos8895-dream2lte_common.dtsi`, `exynos8895-rmem.dtsi`.
- Linux v6.13: `exynos8895.dtsi`, `exynos8895-pinctrl.dtsi`, `exynos8895-dreamlte.dts` (S8 **not S8+**), `clk-exynos8895.c`, pinctrl bank data.

## Run entirely on GitHub Actions

1. Open Actions in this repository.
2. Open `Alice K510 P1A Exynos8895 DTB compile` (or P1B/P1C).
3. Use *Run workflow* and choose branch `research/k510-dream2lte-p1`.
4. Inspect build log and artifact. P1A/P1B DTBs are clearly named `NOT-FLASHABLE`.

Alternatively locally:

```bash
export K510_WORKDIR=/large/external/ssd/alice-k510
bash research/k510/bootstrap.sh --fetch
SRC="$K510_WORKDIR/linux-5.10.262"
bash research/k510/p1-import-dts.sh "$SRC"
bash research/k510/p1-import-pinctrl.sh "$SRC"
bash research/k510/p1-import-clocks.sh "$SRC"
# Standard Linux 5.10 cross-build steps follow; no custom boot image created.
```

## Boot blocker: not ready to flash

The P1 DTB **deliberately lacks verified RAM and reserved-memory maps**. Some memory carveouts in the Samsung 4.4 downstream tree include the modem, secure camera/TEE, display/ION and other secure regions. Do not assume that the upstream S8 (SM-G950F) device's memory map is suitable for the S8+ SM-G955F. Samsung bootloader handoff, DRAM and early UART/pstore, storage, PMIC, regulator/clock dependencies and vendor drivers must be proven first. The P1C clock adapter is a compile/ABI experiment, not proof of hardware clock correctness or suspend/resume behavior.

**No flashable boot.img exists.** Never package the generic `Image` and P1 DTB into a boot partition. Keep the known-working Alice V12R5T kernel 4.4.302 on the phone.

## P1 acceptance

- [x] Create standalone P1 GitHub branch separate from known-good V12.
- [x] Backport DTS and dream2lte DTB make rule into genuine 5.10.
- [x] Pass P1A device-tree compiler on GitHub Actions.
- [x] P1B pinctrl source compile passed on GitHub Actions (hardware GPIO/EINT offsets still need validation).
- [ ] P1C CCF build initially failed: Linux 5.10 missing PLL1051x/1052x; P1C2 adds backported PLL ops + 5.10 API fix. CI revalidation pending. Hardware gate/PLL sequencing NOT verified.
- [ ] Audit actual SM-G955F boot layout and reserved RAM areas; use read-only `research/k510/collect-boot-layout.sh` on the real device and compare with Samsung 4.4 `exynos8895-rmem.dtsi`.
- [ ] Driver-level power-on testing and boot image P2.

## Current critical P1C blocker and remediation

CI P1C run 37963445642 failed because 5.10 does not implement `pll_1051x`/`pll_1052x` and because newer donor used `of_device_get_match_data`. The new script `p1-fix-pll510.sh` imports accurate PLL0822x-family rate programming plus bounded lock checking into 5.10 and switches match-data lookup to `device_get_match_data`. This has **not** yet passed CI or physical clock validation. The original 5.10 4.4 kernel tree was never altered.

Device live boot-layout read-only collection:
```bash
bash research/k510/collect-boot-layout.sh
```
Only run this on the **already-booted known-good V12R5T** using Zorin OS USB ADB. Upload the text report; no partitions are accessed for writing.
