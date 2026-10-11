# K510 P30 on-device log 2026-10-11 — stale pstore evidence

Private source: user-uploaded `K510_P30_LOG_20261011_210903.tar.gz` and prior `K510_P29_LOG_20261011_202940.tar.gz`. Do not commit private logs or serial numbers.

## Verified
- P30 TWRP BOOT SHA256 readback: `e3f15c7ce5c8e49f2db2ae2db1e77b0fd6e6c5d82abe0b0ce35ace7274554a66`; matches CI P30 image.
- Recovery is TWRP 3.7.1_12-0 running Linux 4.4.302, NOT K510 5.10.
- The archive contains nested path `pstore/pstore/dmesg-ramoops-0`, 16332 bytes. `kernel-errors.txt` was empty because the user's grep target used `pstore/*` without recursive nested depth.
- P29 dump SHA256: `248ee02c05bcd99a5d22c7ab993b22bbd4f11b49370a1f457b415fb8d7b829f0`.
- P30 dump SHA256: `b4b959fd49fe09366e2f91e7d4bb08767a91cc0d8dde001214374e8134bce665`.
- Byte comparison: 16,303 / 16,332 identical, 29 changed byte positions; nearly all differ by a *single bit*. Content contains same full kernel initcall series, same `exynos_acpm_binary_update` -> `acpm_ipc_set_waiting_mode+0x10/0x20` -> VA 0x30, same ~0.389s kernel panic and same trace context.
- P29 and P30 pstore files also have the same payload length. A different file digest alone is not evidence of a new panic; the tiny differences look like bit corruption of *old persistent RAM data*.
- Recovery reset reason MPON; no new signature proving P30 entered 5.10 `/init` or emitted ACPM guard warning. Battery 15%, charging.

## Interpretation / safety
- Best-supported explanation: **TWRP recovered stale P29 panic data** after P30 was flashed. DO NOT claim P30 repeated the NULL fault. DO NOT claim P30 succeeded to userspace. The same signature could hypothetically recur, but bit-level near-identity plus identical sequence gives very strong stale-log evidence.
- Preserve both original tarballs; before another controlled hardware experiment take a backup of the existing pstore and verify it. Only after conscious approval consider clearing the archived record via pstore unlink in TWRP, then repeat with a unique P30/P31 boot marker and recover pstore. Deleting pstore files destroys only those diagnostic records but is a write and must be explicitly explained.
- BOOT is still research NO-FLASH by repository audit; UFS remains DT `status=disabled`, ACPM firmware/PMIC runtime unavailable, and no One UI 8 boot evidence.
- If the next run has no new console/pstore, do not assume a Linux panic: early lockups, missing display console, or pstore not retained all remain possible.
