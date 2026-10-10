# P2G-R1 SM-G955F real-device hang: 2026-10-10

## Observation (from user-supplied recovery archive; do not upload private raw logs)

- User reported a test image stuck at initial Samsung Galaxy S8+ splash; device can still enter TWRP.
- Archive ALICE_KERNEL_RECOVERY_LOG.tar(1).gz contains: bootloader.txt, device.txt, kernel-last-kmsg.txt, kernel-dmesg.txt, recovery.log, kernel-version.txt, empty pstore/ subtree.
- `kernel-version.txt`: `4.4.302-android13-9-g5c685b520db3` (TWRP recovery kernel), not Linux 5.10.262.
- `kernel-last-kmsg.txt`: S-Boot 4.0, SM-G955F Exynos8895 rev10, explicitly selects `recovery mode`, loads RECOVERY, successfully reaches `Starting kernel...` for Recovery. It is **not** a trace of the failed BOOT partition execution.
- S-Boot signature verification reports failure on custom RECOVERY, yet successfully starts TWRP. **Do not infer P2G BOOT signature failure from this.**
- `kernel-dmesg.txt`: TWRP ramoops backend registers at physical `0x92000000`, region `0x8000`, but `persistent_ram: no valid data in buffer`. No previous K510 panic or console record was present.
- No evidence of any actual Linux 5.10 execution / initramfs reached. Nor is there affirmative evidence that Linux 5.10 failed **before** execution: an early crash, display-only hang, RAM reset, and pstore misconfiguration may all look identical.
- Archive **does not contain BOOT SHA256**. Confirm image with read-only `adb shell sha256sum /dev/block/by-name/BOOT` while in TWRP. P2G-R1 expected `72f20c54809d7a5c85ce0b82eefdbc410849655215bcbb889f715110995e32b1`; old P2G is `9d0249777962e0d00d8904ef8c594472cd17fd814a94c691ef387e677000dbf4`; stock V12R5T `76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823`.

## New software audit: important root-cause uncertainty

Review of pinned upstream `ivoszbg/uniLoader` commit `1144a9ff7fc9e99ca7f52433f4a02847b44b7051`:

- `configs/dreamlte_defconfig` inherits `CONFIG_POSITION_INDEPENDENT=y`, `CONFIG_TEXT_BASE=0x87000000`, `CONFIG_PAYLOAD_ENTRY=0x90000000`, `CONFIG_RAMDISK_ENTRY=0x84000000`.
- Loader `arch/aarch64/reloc.S` copies itself to TEXT_BASE before running, and `arch/aarch64/load-kernel.c` copies the ARM64 Image to PAYLOAD_ENTRY before branching.
- Loader `lib/Kconfig` defaults `CONFIG_EARLYCON=n`; no explicit `EARLYCON=y` is set by the S8+ derived config. In P2G-R1 the donor simplefb device registration is intentionally disabled because 0xcc000000 overlaps reserved camera memory. **Hence the loader has no verified active log output in this build.**
- Linux 5.10 R1 enables PSTORE_RAM/CONSOLE and adds ramoops 0x92000000 to the Device Tree, but this is only useful after Linux reaches pstore registration. *It cannot record S-Boot or uniLoader faults.*
- CI checks raw `Image` file length < 0x2000000 (distance 0x90000000 -> 0x92000000). This does **not** validate the ARM64 Image header runtime `image_size` or BSS plus early allocations. The actual Image header runtime size and loader BSS should be checked before any another flash.

## Next engineering work

1. Preserve TWRP/Download Mode and known-good V12R5T BOOT. Don't flash repeated identical R1 images.
2. Verify read-only BOOT SHA on actual phone to establish which exact image was tested.
3. Improve static boot-memory collision checks: parse ARM64 Image header (offset 0x10), inspect runtime image size and kernel/loader/initrd/DTB RAM map, compare every reserved memory block including ramoops.
4. Develop staged instrumentation at S-Boot -> uniLoader entry BEFORE Linux, ideally UART via verified Exynos8895 pins/serial/JIG or a thoroughly audited persistent debug ring that TWRP can read. Avoid speculative MMIO writes to PMIC/DECON.
5. Build next candidate only after pre-Linux observability is established and structural checks pass. Passing CI alone does not validate physical boot.

**No private user BOOT image or raw log has been committed to GitHub.**
