# Alice K510 P2 — Exynos8895 / SM-G955F early boot

Target: **Galaxy S8+ SM-G955F rev05**, bootloader **G955FXXUCDZE7**.
Known-good fallback: **4.4.302-Alice-V12R5T**; do not overwrite it.
Linux source: pristine **5.10.262**, with P1 Exynos8895 backports applied in CI.

## Confirmed work

- P1E Linux 5.10.262 ARM64 Image + Exynos8895 Device Tree, pinctrl, PLL/clock, measured RAM: GitHub Actions **37996355242** SUCCESS.
- Physical Device Tree observation: three nonempty RAM ranges, 12 reserved-memory entries. Recorded under `P1D-RMEM.txt`.
- P2 research branch forked without changing V12/P1.
- P2 read-only Android boot header audit tool added: `p2-inspect-boot-header.sh`. Reads **only 4096 bytes** of /dev/block/by-name/BOOT, deletes temporary header, outputs public structural metadata without boot command line / identifiers.
- P2A static ARM64 initramfs and `/init` with distinct `ALICE_K510_P2A_INIT_REACHED` marker staged.
- P2A donor uniLoader at a fixed commit **1144a9ff7fc9e99ca7f52433f4a02847b44b7051**; its `dreamlte` target is for **SM-G950F**, not the user's SM-G955F. Build for toolchain/firmware-interface research **only**.

## Mandatory blockers before delivering boot.img

1. **S8+ loader target:** port actual SM-G955F rev05 board init/PMIC and verify memory target addresses, not simply rename SM-G950F uniLoader.
2. **Android boot header/DT packing:** inspect actual stock boot format and validate output offsets/base/page size before any packer runs; preserve original ramdisk/recovery chain where required.
3. **DT reservation semantics:** P1D all-no-map is a conservative compiler placeholder. Vendor camera/TEE/modem DMA and the old /memreserve need audits before hardware boot.
4. **Evidence of early boot:** initramfs output via UART or pstore; prepare deterministic rollback to V12R5T from recovery/Download Mode.
5. **UFS/PMIC/display/touch/USB:** currently not ported/verified, and required for Android 16 system operation.

Successful cross compilation does not imply device boot. P2A deliberately uploads **logs only**, not a flashable kernel or an Android boot.img.

## Evidence and further references

- [P1E full cross-build](https://github.com/HaloT455/dream2lte-45/actions/runs/37996355242)
- [Exynos8895 Linux bring-up 2024](https://lists.openwall.net/linux-kernel/2024/09/09/753)
- [uniLoader source](https://github.com/ivoszbg/uniLoader)

## P2B SM-G955F uniLoader target

A separate script `p2-adapt-uniloader-dream2lte.sh` creates an explicit `CONFIG_SAMSUNG_DREAM2LTE` target, based on the upstream Galaxy S8 (non-plus) board code, and deliberately disables unverified S2MPS17 LDO and DECON register writes. Build test is `.github/workflows/k510-p2b-uniloader.yml` run 37998876604 using **invalid dummy payloads**. This is an independent compiler test, not evidence of bootability. Full real-payload integration is deferred until P2A and P2B compile gates pass.

## P2C stock BOOT header audit (2026-10-10, 05:27 +07)

The SM-G955F rev05 user provided a **read-only** 4096-byte BOOT header analysis, not the complete boot partition image. Structural fields:

- `kernel_size=38149864` (`0x2461ee8`), `ramdisk_size=700389` (`0xaafe5`), `second_size=0`.
- `page_size=2048`, `dt_size_or_header_version=229376` (`0x38000`).
- `kernel_addr=0x10008000`, `ramdisk_addr=0x11000000`, `tags_addr=0x10000100`.
- Likely **legacy pre-versioned Android boot image**, where header offset `0x28` contains a DT size, **not** header_version; this classification remains conditional until full-image disassembly.
- Assuming that layout, minimum padded image size is **39,081,984 bytes** (header 2048; kernel 38,150,144; ramdisk 700,416; DT 229,376). This is not the BOOT partition size and does not account for vendor tails/signatures.
- **All three load addresses lie outside the RAM ranges exposed in P1D live Device Tree**, suggesting Samsung S-Boot load/relocation or header semantics need independent proof. Hard blocker for any safe boot.img packaging.
- The named boot image and any cmdline were deliberately excluded from checked-in data.

CI `.github/workflows/k510-p2c-boot-header.yml` checks the report against the observed RAM ranges; run **37999483504** passed. Still, a successful metadata check is **not** proof that the produced kernel can boot on hardware.

Separately, P2A upstream S8 donor-target boot-lab build run **37998477822** completed successfully (Image, DTB, static ARM64 initramfs and donor uniLoader compile). An SM-G955F-specific loader was compiled in P2B. P2C integrated SM-G955F real-payload build remains a separate CI gate.

**NO BOOT IMAGE HAS BEEN RELEASED. DO NOT FLASH THE CI COMPILATION ARTIFACTS.**

## P2D read-only stock BOOT boundary verification

The user provided only an analyzed 4096-byte BOOT header; this is insufficient to verify the embedded 229376-byte DT payload, trailing vendor/signature data, exact full partition size and Samsung-specific packing. A read-only local backup/structural verifier was added at `research/k510/p2d-read-only-backup-boot.sh`. The script verifies the Exynos8895 + SM-G955F identity, copies the **existing known-good BOOT** to an image on the user’s laptop, checks the exact partition size, then emits a small text-only structural report. It does NOT write to the phone and intentionally avoids printing cmdline and embedded identifiers. Keep the local raw BOOT backup private and do not upload it unless specifically required.

The boot-header metadata compiler audit passed in [P2C run 37999483504](https://github.com/HaloT455/dream2lte-45/actions/runs/37999483504). The full P2C cross-build run 37999002645 is separate and not yet confirmed complete here. **Do not claim that any of these tests validate device boot.**

## P2E full BOOT binary structural audit — DONE

User supplied the complete **40 MiB** read-only stock BOOT backup in conversation. It was examined locally; raw binary **NOT uploaded to public GitHub**. Sanitized technical results are in `P2E-STOCK-BOOT-AUDIT.md`.

- Primary `DTBH` v2 FDT container at 38,852,608, Exynos8895, SM-G955F rev05.
- **Identical repeated DTBH** at 39,106,560, outside the header-declared DT section.
- Samsung `SEANDROIDENFORCE` marker at 39,335,936.
- Last-64-byte AVBf-looking marker has metadata pointer inconsistent with current BOOT: `AVB0` is absent at claimed vbmeta offset. This is NOT verified AVB.
- ARM64 raw Image and gzip ramdisk placement verified. Loader header addresses are still not proven valid physical Linux addresses.
- P2E `p2e-inspect-boot.py` is a read-only LOCAL inspector. Synthetic fixture workflow `.github/workflows/k510-p2e-stock-layout.yml` **passed** in GitHub Actions run 38000312222. The CI saw **only synthetic bytes**, not the user's backup.

**NO FLASHABLE BOOT.IMG IS VERIFIED OR PROVIDED.** Porting Exynos8895 storage/PMIC and proving Samsung S-Boot handoff remain blocking.
