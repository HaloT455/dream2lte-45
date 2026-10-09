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
