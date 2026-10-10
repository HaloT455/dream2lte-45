# K510 P2G-R3: evidence and controlled visible-loader experiment

## Why R3

R1 and R2 both remained on static Samsung Galaxy S8+ logo; BOOT SHA-256 confirmed both were flashed, TWRP 4.4.302 still boots, and no Linux 5.10 pstore records survived. Static logo cannot distinguish S-Boot rejection, uniLoader failure, or Linux early startup.

The upstream Exynos8895 / Galaxy S8 dreamlte mainline Device Tree explicitly defines **continuous splash framebuffer** at `0xcc000000` (`1440 * 2960 * 4` bytes), in addition to ramoops `0x92000000`. The upstream S8 Linux port also documents Samsung S-Boot's DECON trigger problem and the need for uniLoader; this is an evidence-based *candidate* for the static display issue. On this SM-G955F, TWRP cmdline contains `s3cfb.bootloaderfb=0xcc000000`. The R1/R2 code disabled both donor DECON trigger and simplefb, inadvertently leaving no working visible progress channel. However, this does NOT prove an early kernel hang was merely a display issue.

Sources:
- https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/7acf90feab8b009fde7def08ff2c622d0f10e99f/arch/arm64/boot/dts/exynos/exynos8895-dreamlte.dts
- https://lists.openwall.net/linux-kernel/2024/09/09/753
- https://github.com/ivoszbg/uniLoader at pinned commit `1144a9ff7fc9e99ca7f52433f4a02847b44b7051`

## R3 experimental changes

- Restore the **donor S8** register write to `0x12860070` (DECON trigger control), enabling framebuffer refresh. This is an **unvalidated MMIO write on SM-G955F**; it is experimental and may make the device hang or change the display.
- Re-enable `simplefb` registration only during the uniLoader probe on the bootloader continuous splash buffer at `0xcc000000`. Do NOT activate camera drivers or new PMIC sequences. Note the reserved framebuffer overlaps the legacy camera carveout in the TWRP DTS; mainline treats it as a distinct reserved splash allocation.
- Print `ALICE_R3_STAGE_A_UNILOADER_VISIBLE` after simplefb initialization.
- Print `ALICE_R3_STAGE_B_KERNEL_HANDOFF` immediately before calling `boot_kernel`.
- Leave the R2 kernel memory layout, Linux kernel binary, pstore mapping, and experimental `/init` unchanged to isolate the framebuffer observation.
- Keep donor PMIC/s2mps17 writes disabled, preserving that safety gate. Does **not** integrate Android System, Vendor or offline charging.

## Stock BOOT structure: independently verified from user's original local 40MiB backup

The original working V12R5T BOOT (SHA `76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823`) and R2 share `ANDROID!` magic, `kernel_addr=0x10008000`, `ramdisk_addr=0x11000000`, `second_addr=0x10f00000`, `tags_addr=0x10000100`, and `page_size=2048`, and `board=SRPPK02A007KU`. This reduces suspicion that simple address/header field mismatch is the only cause.

Differences: original DTBH size `0x38000` (one matching Exynos8895 entry, 227328-byte FDT slot), R2 DTBH size `0x6000` (one matching entry); original header OS-version word at offset `0x2c` is `0x1a0001a5` (Android 13.0.0 2026-05), R2 has zero. Neither difference is yet proven boot-critical. Do not copy the user's private kernel, ramdisk, nor Device Tree into GitHub.

## R3 experiment interpretation

- If the screen prints **STAGE_A**: S-Boot loaded and executed enough uniLoader to probe simplefb.
- If also **STAGE_B**: loader reached pre-Linux handoff.
- If STAGE_B prints then hangs: suspect ARM64 entry/DTB/initrd/early Linux path; a marker printed *before* branching does not prove actual Linux execution.
- If screen never changes: still ambiguous (S-Boot can reject image, uniLoader may fail, or DECON/framebuffer may not be functional).
- If loader prints text but Android never starts: expected — the debug initramfs is a heartbeat-only process, not Android Init.
- If black screen or unusual heating: stop, restore previously verified V12R5T BOOT using TWRP.

CI can validate compile, presence of stage marker strings, boot-image packing and static RAM ranges; it **cannot** prove actual device boot or safety of DECON MMIO write.

Do not merge into stable kernel branch and do not modify SYSTEM, VENDOR, EFS, or RECOVERY partitions.
