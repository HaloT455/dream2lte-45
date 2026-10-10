# P2G-R2 real-device early-boot result — SM-G955F, 2026-10-10

## Verified evidence (from private user-supplied logs; not uploaded to GitHub)

User tested R2, saw the static Samsung Galaxy S8+ logo, then entered TWRP and collected `ALICE_K510_R2_LOG.zip` and `ALICE_K510_R2_20261010-101903.tar.gz`. Both archives have **21 identical file contents**.

- **BOOT SHA-256 read directly from /dev/block/by-name/BOOT**: `a65f5108f61578d2c3926219f931edd5394f47c86c44cf93cb2df55ccbef712b`, exactly matching P2G-R2 CI #38008674962. BOOT target is `/dev/block/sda7`.
- BOOT header (4KiB capture) begins `ANDROID!`; `kernel_size=0x1ed1168`, `kernel_addr=0x10008000`, `ramdisk_size=0x3d755`, `ramdisk_addr=0x11000000`, `page_size=2048`, `dt_size=0x6000`. Header fields have **not** been proven compatible with real S-Boot BOOT handoff.
- TWRP kernel: `Linux 4.4.302-android13-9-g5c685b520db3`, **not** P2G's Linux 5.10.
- `/sys/fs/pstore` empty. TWRP dmesg shows `persistent_ram: no valid data in buffer (sig = 0x42070244)`, `pstore: Registered ramoops as persistent store backend`, `ramoops: attached 0x8000@0x92000000, ecc: 0/0`.
- `/proc/last_kmsg` records **S-Boot selecting recovery mode** (`mach_board_main: recovery set!`), validating custom RECOVERY signature and calling `Starting kernel...` for **TWRP**, not for failed P2G-R2 BOOT.
- `/proc/reset_reason` is `MPON` — not evidence of a Linux 5.10 panic.
- `/proc/boot_stat` reaches `late` during the successfully booted TWRP 4.4 kernel, not Linux 5.10.
- S-Boot RECOVERY log's `Verify_Signature_With_Signingtype: failed` concerns custom recovery, which boots; cannot infer that R2 BOOT was rejected.
- No trustworthy `K510`, `uniLoader`, or Linux 5.10 panic record was retrieved. NO evidence identifies the precise stage of hang.

## Status of R2 change

R2 CI passed: relocated raw Linux kernel to `0x98000000` (ARM64 Image `text_offset=0x0`), `image_size=0x1f10000`; guarded `[0x98000000,0x9c000000)` as runtime. Static reserved-memory checks passed. However **passing static check did not fix the real boot hang**. The previously suspected ESS overlap was a *hypothesis*, not a confirmed root cause.

## Next actions — do not blindly flash R2 again

1. Confirm exact S-Boot handling of legacy Android `kernel_addr` versus the actual loaded stage at ROM/S-Boot and initial uniLoader PC; avoid asserting `0x10008000` must be executable DDR without direct evidence.
2. Instrument pre-Linux execution with tested UART wiring / read-only CPU debugger, or audited persistent milestones that survive warm reboot and do not corrupt ramoops or vendor firmware buffers. `CONFIG_EARLYCON=n` in pinned uniLoader donor; R1/R2 disabled simple framebuffer, so no verified pre-Linux console.
3. Ensure boot image's dtbh and handoff register conventions match hardware rev10, as well as loader rebase to `0x87000000`. Never enable unverified PMIC or DECON MMIO writes.
4. Only after obtaining useful stage evidence should the team produce R3 for another real-device test. Retain full verified V12R5T boot recovery path.

Important: An empty pstore can mean failure before its registration, RAM erasure from cold reset, incompatible persistent layout, or no crash. Do not claim it proves Linux 5.10 never executed.
