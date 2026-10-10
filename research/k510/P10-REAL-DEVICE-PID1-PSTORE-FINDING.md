# P10 real-device result: Linux 5.10 PID1 observed through persistent RAM

## Provenance and limitations

The user tested the **P10** experimental BOOT on Samsung Galaxy S8+ SM-G955F on 2026-10-10, then rebooted to their TWRP (Linux 4.4.302) and collected `K510_P10_LOG_20261010_141918.tar.gz`. **Do not commit private raw archives, identifiers or proprietary boot backup.**

On-device BOOT SHA-256 is `050d25691e260fa4e47737b26a2ff564d05d341693dcd44618b0358e79ef089b`, **exactly equal** to P10 GitHub Actions #38032624999. A photo clearly shows the last screen line `ALICE_P10_READY_TO_BRANCH` after all P8/P9 markers and `ALICE_P10_DAIF_ALL_MASKED`, `ALICE_P10_KERNEL_CACHE_READY`, `ALICE_P10_RAMDISK_CACHE_READY`, `ALICE_P10_DTB_CACHE_READY`.

Unlike previous trials, Recovery mounted a **new recovered pstore file** `/sys/fs/pstore/pmsg-ramoops-0`, 16372 bytes. TWRP dmesg reports `persistent_ram: found existing buffer, size 16372, start 2470` and `ramoops: attached 0x8000@0x92000000`. The pstore bytes contain widespread bit corruption; do not treat the contents as perfect evidence of every driver state.

### High-value excerpt (unaltered snippets except truncated corrupted bytes)

- `[   17.930641] Freeing unused kernel memory: 6144K`
- `[   17.934404M Run /ini4 as init process` (corrupted text, still strongly recognizable as Run /init)
- `[   17.940913]     /init`
- `[   17... ] ALICE_K510_P2A_INIT_REACHED Hinux 5.10` (contains exact private P2A debug init marker, corruption in word Linux)
- `[...17.956262] ALICE_C510[P2A_HEART... `
- `[...27.9... ] ALICE...P2A_HEART...` (timestamp corruption; context suggests subsequent heartbeat)
- `[   57.)60134] ALI...K510...HEART...EAT`

The debug P2A `/init` unconditionally logs `ALICE_K510_P2A_INIT_REACHED Linux 5.10` followed by `ALICE_K510_P2A_HEARTBEAT` every 20 seconds. These signatures, `Run /init`, and continuity of timestamps are **strong evidence Linux 5.10 reached user PID1**, possibly survived ~58 seconds. Historical pstore persistence prevents proving P10 alone originated every byte, but P9's previous pstore was empty, and P10 BOOT was independently verified.

`last-kmsg.txt` and live `recovery-dmesg.txt` include old/corrupted Samsung downstream logs and **TWRP Recovery** startup, NOT trustworthy Linux 5.10 BOOT console. Do not claim vendor GPU/display, battery/charging or UFS function from those logs.

## Engineering conclusion

- **STOP claiming static uniLoader display means Linux fails at handoff.** P10 may boot Linux and run `/init` while still showing uniLoader's unchanged framebuffer because mainline K510 has no functioning DECON/DSIM panel driver.
- P10 demonstrates CPU, memory, interrupts, kernel and debug PID1 can function long enough to write heartbeats, subject to the provenance caveat above.
- P10 **does NOT** mount EROFS system/vendor, run Android 16 init, enumerate UFS (P4 UFS DTS `status = "disabled"`), operate MAX77865/S2MPS17, restore offline charging, or drive the physical panel after uniLoader.
- Prioritize source/API-backed **PMIC/ACPM → UFS PHY/calibration → read-only UFS enumeration → Android first-stage init**, parallel DECON/DSIM console/graphics bring-up; leave GPU, camera, modem disabled until foundations exist.
- Because pstore content is corrupt, align ramoops layout/config between 5.10 and TWRP and increase observability without overwriting unrelated reserved physical regions. An uncorrupted trace with boot-version marker and PID1 counter/uptime will be needed for definitive repeatability.
- Preserve working V12R5T BOOT, recovery and download mode. No new P11 experimental BOOT should be flashed without bounded compile/runtime evidence.

## Verified history

- P7: loaded uniLoader to `Booting kernel...`, no pstore evidence.
- P8: Image and ramdisk sample copy verified; `BEFORE_ARM64_BRANCH` on screen.
- P9: EL1, MMU off, I/D cache control bits set, DAIF.A unmasked; no recovered pstore.
- P10: DAIF all masked and copied Image/ramdisk/FDT cache maintenance completed, kernel PID1/heartbeat trace now recovered.

**Recommended P11:** upgrade observable 5.10 boot evidence and validate driver dependency preconditions. Do not present as full port of One UI 8.
