# P28 SM-G955F on-device test — 2026-10-11

Evidence: user's private `K510_P28_HANDOFF_20261011_195314.tar.gz` and screen photo. This is a **sanitized research summary**. Do NOT commit raw logs, ADB serial, private boot data or unique device identifiers.

## Grounded result

- On-device TWRP readback of `/dev/block/by-name/BOOT` has SHA-256 `2343796be945e41369e8cc1db0572ae1205c20c1d28d2094a714cbef203cbd02`, identical to P28 CI produced 40-MiB diagnostic BOOT.
- Screen shows `simplefb: ready (1440x2960)`, `passed board initialization`, `ALICE_R3_STAGE_A_UNILOADER_VISIBLE`, `ALICE_R3_STAGE_B_KERNEL_HANDOFF`, then `trying to open fdt...`, `adding linux,initrd-start...`, `adding linux,initrd-end...`, `Booting kernel...`. This proves uniLoader reached its handoff call, NOT that Linux 5.10 executed.
- User reports the screen remains at `Booting kernel...`; no Linux console shown.
- TWRP successfully entered after trial: `Linux 4.4.302-android13-9-g5c685b520db3`. **This is recovery Linux 4.4, not P28 Linux 5.10.**
- `/sys/fs/pstore` is empty; the generated `k510-markers.txt` is zero bytes; no recovered 5.10 PID1 heartbeat / console trace.
- TWRP `dmesg`: two `persistent_ram: no valid data in buffer` reports (observed signatures `0x43454244` and `0x42070244`), then `ramoops: attached 0x8000@0x92000000`.
- `/proc/last_kmsg` is S-Boot's **RECOVERY** path and ends at starting the TWRP kernel, not an observed failed P28 BOOT kernel log. It reports S-Boot/Recovery UFS initialization, which **does not establish Linux 5.10 UFS runtime**.
- `/proc/reset_reason` = `MPON`. This alone cannot establish an arm64 Linux exception or boot failure stage.

## Interpretation

The frozen uniLoader text cannot differentiate a kernel that did not branch, an early fatal hang, and a kernel that runs but has no functional panel console. Missing pstore may also mean RAM was cleared on reset or pstore never initialized. These findings **do not prove** Linux 5.10 crashed, and do not identify any active UFS root cause: its DT node is disabled.

P10 on-device experiment (prior `P10-REAL-DEVICE-PID1-PSTORE-FINDING.md`) showed strong, though corrupted, Linux 5.10 `/init` heartbeat traces after P8/P9/P10 handoff fixes; P28 omitted `ALICE_K510_P8_COPY_CHECK=1`, `ALICE_K510_P9_CPU_PROBE=1`, `ALICE_K510_P10_FIX_HANDOFF=1` during uniLoader build. This is a concrete regression candidate, **not** a confirmed causal diagnosis.

P29 re-enables those three flags in a fresh CI and checks expected ELF text markers. Do not flash until P29 real Image, DTBH, uniLoader and 40-MiB BOOT packaging all pass. Preserve verified original V12R5T BOOT as offline recovery. Do not turn on UFS or write userdata/system/vendor/EFS.
