# K510 P9 device evidence and P10 ARM64 transfer correction

## Exact evidence from G955F user test, 2026-10-10

Uploaded original log: `K510_P9_LOG_20261010_135001.tar.gz`. This remains user-local; **do not add the personal log or identifiers to public GitHub**.

- On-device BOOT SHA-256 `a5d9373bd1c53a6fd4f441efe1da851a84caea0b182daaf7464073c3c9493359` equals P9 CI #38030530330 boot-image-structure digest.
- TWRP session is Linux `4.4.302-android13-9-g5c685b520db3`. Booted **RECOVERY**, not Linux 5.10.
- TWRP `/sys/fs/pstore` and adb pull of pstore both **empty**. Its `dmesg` registers ramoops `0x92000000` but prints `persistent_ram: no valid data in buffer` (signature mismatch).
- `/proc/last_kmsg` exactly 2,097,152 bytes, includes corrupted old downstream 4.4 log samples and later S-Boot **RECOVERY** DTBH boot, not verifiable K510 Linux 5.10 crash data. No `ALICE_` or `Linux version 5.10` markers there.
- Battery in TWRP: 88%, `status=Charging`, USB online=1, voltage 4.125V. This does not validate charging in experimental P9.
- P9 phone photo independently shows all P8 copy-verification markers and `ALICE_P9_ENTRY_EL_1`, `ALICE_P9_MMU_0_DCACHE_1_ICACHE_1`, `ALICE_P9_DAIF_D1_A0_I1_F1`, `ALICE_P9_DTB_ALIGN8_1`, `ALICE_P9_STATE_READ_DONE`, `ALICE_P8_BEFORE_ARM64_BRANCH`. **No Linux 5.10-origin log was observed.**

## Why P10 focuses on handoff

ARM64 Linux 5.10 boot contract: `Documentation/arm64/booting.rst` in upstream v5.10.262, https://github.com/gregkh/linux/blob/v5.10.262/Documentation/arm64/booting.rst

Required before transfer:
- primary CPU EL1(non-secure) or EL2, MMU off, x0 physical FDT, x1/x2/x3 zero;
- interrupts **all masked** in PSTATE.DAIF, including asynchronous SError;
- copied Linux Image **cleaned to PoC**, no stale kernel instruction cache entries;
- DTB 8-byte aligned and no more than 2MB, initrd described and memory resident.
- `SCTLR_EL1.C = 1` observed while MMU is off is a register bit; by itself does NOT prove active cacheability of all data accesses.

P9 showed `DAIF.A = 0` which directly violates the documented condition. P8 verified only head/tail samples of copied buffers, not PoC cache writeback.

## P10 implementation, NOT hardware-validated

- Build on exact P9 binary-source/DTB/P5 Android-core composition.
- After P8 copy sample checks, ensure `msr DAIFSet, #0xf`, read-back checks all four masks, print `ALICE_P10_DAIF_ALL_MASKED`.
- Derive D/I-cache line sizes from `CTR_EL0`; clean Image, initramfs and patched FDT ranges with AArch64 `dc cvac` to PoC, invalidate copied Image instruction cache with `ic ivau`, synchronise via `dsb sy`/`isb`. Each phase prints a marker; fail closed on FDT format/size or out-of-range line sizes. FDT is parsed read-only for standard magic and totalsize.
- No MMU enable/disable, no exception-level changes, no arbitrary PMIC MMIO, no UFS activation. UFS remains disabled; Android `/init` is still debug heartbeat, not One UI 8.
- **Compiler/static CI success cannot establish correct real-device boot.** No phone partition is ever written by CI.

## Interpretation of next hardware test

- Last line `ALICE_P10_DAIF_ALL_MASKED`: stop in cache-clean range or earlier.
- Last line `ALICE_P10_KERNEL_CLEAN_BEGIN`: Image data cache clean may fault; verify RAM/cache attributes before further action.
- `ALICE_P10_KERNEL_CACHE_READY` + `RAMDISK_CACHE_READY` + `DTB_CACHE_READY` then `READY_TO_BRANCH`: architected maintenance returned. A subsequent hang still can mean Linux entry assumptions violated or no early kernel instrumentation.
- Linux `ALICE_K510_P2A_INIT_REACHED` from **verified 5.10 log**: Linux reached debug init, *not Android*.
- Empty pstore after reboot remains inconclusive.

## Rollback

Only consider a hardware test with verified known-good V12R5T BOOT backup SHA-256 `76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823`, working TWRP/Download Mode, and an attended recovery plan. This unverified experimental P10 can hang, blank the screen, or disrupt off-mode charging. Do not flash EFS/CP/VENDOR/SYSTEM/USERDATA.
