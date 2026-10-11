# K510 P29 hardware kernel panic and P30 fix — 2026-10-11

Evidence: user privately uploaded K510_P29_LOG_20261011_202940.tar.gz, and screen photo. Do NOT upload raw personal logs or the original BOOT image to GitHub.

## Verified device result

- BOOT readback SHA-256 9526ff20c1923652128ff33e4c7e60b91b747b711745bb11d0cd3fca4be1f753 exactly matches P29 CI #38140878315.
- UniLoader visibly completed P8 kernel/ramdisk copy checks, P9 EL1/DAIF inspection, and P10 DAIF all-masked/cache maintenance, ending at ALICE_P10_READY_TO_BRANCH.
- Recovery uname=Linux 4.4.302, but dmesg-ramoops-0 is a new 16332-byte kernel panic trace from experimental Linux 5.10. Text is bit-corrupted yet named kernel symbols and PC/LR are legible.
- Recovered pstore reports initialization functions running, then NULL pointer data abort at virtual address 0x30.
- PC: acpm_ipc_set_waiting_mode+0x10/0x20; LR: exynos_acpm_binary_update+0x4c/0x2d8.
- Final panic: Attempted to kill init! exitcode=0x0000000b at ~0.393 s.
- CPU0 PID1 was the in-kernel initialization process. No proof that the debug userspace /init ran.
- Hardware name in pstore: Samsung Galaxy S8+ (SM-G955F) Linux 5.10 research (DT).
- Reset reason MPON alone is not diagnostic.

## Exact donor source fault

Pin 3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3, drivers/soc/samsung/acpm/acpm.c: fs_initcall_sync(exynos_acpm_binary_update) unconditionally invokes acpm_ipc_set_waiting_mode(BUSY_WAIT), then plugins_init(). ACPM IPC source acpm_ipc.c maintains static acpm_ipc pointer initially NULL. Its setter directly dereferences acpm_ipc->w_mode. On the Linux 5.10 research DT, the native ACPM firmware IPC has not probed, producing the observed NULL+0x30 crash. plugins_init would also dereference unset firmware/memory globals.

## P30 guard and limitations

Stage research/k510/p30-stage-acpm-null-guard.py AFTER P16 into a disposable Linux 5.10.262 build. P30 permits acpm_ipc_runtime_ready() only after successful channel_init, rejects acpm_ipc_set_waiting_mode on uninitialized IPC, and skips unsupported ACPM plugin update if control/firmware/IPC unavailable. Additional alice,acpm-plugin-firmware-reviewed DT opt-in absent, blocking unreviewed firmware writes. Retain P8/P9/P10 ARM64 handoff fixes. UFS DT status=disabled, fixed GPIO VCC, PMIC/S2MPS17 firmware and UFS runtime still unverified.

Compiler/linker success can only demonstrate the specific guard built; the next physical test needs pstore to determine whether later initcalls or /init run. The P29 panic is a real Linux 5.10 kernel fault, not merely uniLoader freezing or Android userspace failure. Do not claim Android/One UI 8 boots.

Preserve separate original V12R5T 40MiB BOOT backup (expected SHA256 76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823) and TWRP/Download Mode. P30 artifact remains research NO-FLASH until successfully built and separately reviewed for a bounded hardware test.
