# ALICE K510 P2G — Experimental early-boot image for Samsung Galaxy S8+ SM-G955F

> **UNVERIFIED ON HARDWARE. Bootloop / black screen likely. Not Android 16 or One UI.**

## What the CI builds

GitHub Actions workflow `.github/workflows/k510-p2g-experimental-boot.yml`:

1. Downloads **actual Linux 5.10.262** source, stages Exynos8895 platform DTS, pinctrl, clock/PLL backports, actual SM-G955F rev05 observed RAM and reserved-memory topology.
2. Builds a standard ARM64 kernel `Image` and experimental `dream2lte` DTB with `rdinit=/init`.
3. Builds a tiny statically-linked ARM64 heartbeat `/init` in gzip initramfs.
4. Builds a **dedicated but hardware-unverified dream2lte** uniLoader board target from a pinned upstream loader source. Its Samsung PMIC/DECON writes are deliberately disabled because physical compatibility is not yet audited.
5. Embeds the Linux 5.10 kernel/DTB/initramfs in uniLoader, and independently adds Samsung DTBH v2 to a legacy Android BOOT image using **2,048-byte pages**, matching original SM-G955F header format.
6. Outputs an **unsigned exactly 40 MiB** `Alice_K510_P2G_SM-G955F_EXPERIMENTAL_boot.img` plus hashes and report, *only if the entire CI build and structural validation succeed*.

Actual BOOT header geometry sourced from user's read-only original 40 MiB BOOT backup; no private backup or data are ever uploaded to GitHub:
`kernel_addr=0x10008000`, `ramdisk_addr=0x11000000`, `tags_addr=0x10000100`, `page_size=2048`, Android legacy `dt_size` at 0x28.

The intended payload loader executes from Samsung S-Boot, then tries to jump to a Linux 5.10 entrypoint. **This handoff is NOT verified.** Android-specific storage, camera, modem, GPU and Wi-Fi support are absent.

## Essential restrictions

- **Only SM-G955F Exynos8895 rev05.** Not SM-G950F, snapdragon variants, or devices with different hardware maps.
- Do not flash unless the user separately confirms a working Recovery/Download Mode and verified offline restoration of the original known-good V12R5T BOOT image.
- This device does not support the ordinary fastboot `boot` method for temporary boot. Any real test would replace the BOOT partition and must have a rollback path.
- Do not flash to RECOVERY, MODEM, EFS, USERDATA or SYSTEM. Never touch partitions other than BOOT for this kernel test.
- The known-good BOOT SHA256 is `76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823`. **Preserve original offline.**
- Bootloader may reject this unsigned image. Absence of display/USB ADB does not prove it never reached `/init`.
- Early UART/pstore logging is not yet validated; success/failure may be difficult to diagnose.
- This is a research image for a user willing to test; **not recommended as a daily ROM kernel**.

CI file artifacts are on the GitHub Actions run page under Artifacts after successful completion. CI itself does not flash anything and runs without access to the user's phone.
