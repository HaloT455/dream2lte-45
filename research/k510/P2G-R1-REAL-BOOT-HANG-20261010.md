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

## Additional read-only evidence: ALICE_K510_R1_EXTRA + ERRORS

Verified from on-device BOOT SHA (recovery read-only): `72f20c54809d7a5c85ce0b82eefdbc410849655215bcbb889f715110995e32b1`. This **exactly matches** successful P2G-R1 GitHub Actions run 38004847699. Recovery is TWRP 4.4.302; `/proc/last_kmsg` is an S-Boot RECOVERY handoff, not failed P2G BOOT. Pstore directory is empty. Reset reason `MPON` alone does **not** identify a K510 kernel panic. `ALICE_K510_R1_ERRORS.txt` is a grep of recovery log for watchdog/reset/panic keywords, not an independent exception trace. `/proc/boot_stat` reports TWRP kernel initcall stages to late, not Linux 5.10.

New important RAM collision **risk**, not yet causal proof: actual R1 raw Linux 5.10 ARM64 Image size in CI is `31,980,032 = 0x1e7fa00` bytes and donor uniLoader copies it to `CONFIG_PAYLOAD_ENTRY=0x90000000`. Thus written binary extent is `[0x90000000, 0x91e7fa00)`. Recovery S-Boot-provided cmdline contains `ess_setup=0x91200000`, **inside** that payload extent. It also names `sec_avc_log` 0x92202000, `sec_tsp_log` 0x92244000, `sec_debug.base` 0x92286000, `auto_summary_log` 0x92388000. These parameters are from the RECOVERY command line and do not prove that the failed P2G BOOT uses identical reservations. Nevertheless, the next build must **not assume** the area 0x90000000..0x923fffff is disposable RAM. Investigate Samsung ESS region lifetime, memory ownership, and verify the ARM64 Image header runtime image_size before relocating. No arbitrary MMIO writes or uncontrolled memory reads recommended.

The raw binary ends **0x180600 bytes** before the reserved R1 ramoops at `0x92000000`; CI's length test only proves the binary extent, not all runtime allocations. The `pstore` directory being empty does not distinguish firmware/loader failure, Linux early panic, RAM clearing on reset, and display-only hangs.

Do not repeat the same uninstrumented R1 flash. Next candidate should pass static exclusion tests for Samsung debug buffers and obtain a pre-Linux observable progress marker.
