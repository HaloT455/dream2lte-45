# P7 boot-gate field test: Exynos8895 SM-G955F (NOT One UI)

CI [P7](https://github.com/HaloT455/dream2lte-45/actions/workflows/k510-p7-android-first-boot-gate.yml) builds a research 40MiB BOOT with
- real Linux **5.10.262**;
- baseline Exynos8895 P1/P2 backports + **P4** UART, GPIO, oscillator and guarded UFS device tree (UFS remains `status=disabled`);
- native Linux 5.10 **P5** Android Binder, EROFS/F2FS, DM and SELinux kernel configuration;
- experimental S8-family **R3** uniLoader frame-update and visible stage markers;
- minimalist `rdinit=/init` heartbeat program. **NOT Android Init.**
None of the original V12R5T vendor GPU, camera, charger or PMIC drivers are ported by P7.

## Interpretation of one short, attended hardware boot experiment

| Screen outcome | What can be concluded | What cannot be concluded |
|---|---|---|
| `ALICE_R3_STAGE_A_UNILOADER_VISIBLE` printed | S-Boot entered uniLoader and simplefb driver can write text | Linux 5.10 started |
| Also `ALICE_R3_STAGE_B_KERNEL_HANDOFF` | uniLoader reached the call to transfer execution to kernel | CPU branched successfully into Linux |
| Neither marker; only original splash | No visible diagnostic evidence | S-Boot rejected boot image, loader crashed, or display update itself failed |
| Black screen | Display controller/framebuffer handoff changed | Android or Linux reached PID1 |
| Linux `ALICE_K510_P2A_INIT_REACHED` in verified 5.10-origin console/pstore | Linux 5.10 reached userspace PID1 | Android/One UI started |
| Recovery TWRP `uname -r = 4.4.302` and empty pstore | Recovery boot works, but no retained 5.10 pstore | **NOT** proof 5.10 never executed |

Do NOT expect animation or Android home screen; P7 intentionally has no vendor/system mounting and no Android framework boot.

## Non-negotiable safety gates

1. Save stock V12R5T **40MiB BOOT** SHA-256 `76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823` to X270. Must verify both SHA and exact filesize **before** experimenting. Preserve TWRP and confirm Download Mode works.
2. Use only artifact for the **successful** P7 CI run; unpack locally and run `bash research/k510/p7-preflight-zorin.sh /artifact/directory /full/path/to/original-V12R5T-BOOT.img`. This command is READ-ONLY and aborts on checksum mismatch, wrong model, kernel not recovery 4.4 or battery below 50%.
3. P7 deliberately re-enables **donor S8 DECON MMIO write** at `0x12860070` and framebuffer `0xCC000000`; real S8+ safety not validated. This may blank display, hang or prevent charging in off-mode. STOP trial if heating abnormal. No unattended experiments; do not write modem/EFS/vendor/system.
4. If a manual BOOT-only flash is later performed after user verifies recovery plan, observe for just several minutes, photograph any stage marker, then return to TWRP to read pstore and verify BOOT SHA. Do not rely on `/proc/last_kmsg` from Recovery to represent failed BOOT.
5. If failure, restore **only** the verified original BOOT with a trusted recovery flash mechanism. Do not erase user data, EFS, modem, Recovery, or bootloader.

## Decision after P7

- Stage A only: debug uniLoader path, board init and memory copies.
- Stage B only: debug ARM64 entry, EL, FDT handoff, RAM placement and early kernel instrumentation.
- Stage C (5.10 PID1): proceed to PMIC/ACPM + UFS PHY port, next Android initramfs; only after storage boots add panel, GPU, camera and peripheral HAL.
- No visual marker: use hardware UART/verified JTAG or boot shim with independent evidence; do not jump directly to vendor driver port based on static splash.

No full V12R5T-to-5.10 port or reliable Android boot is claimed.
