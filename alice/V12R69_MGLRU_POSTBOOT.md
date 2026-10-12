# V12R69 optional One UI MGLRU post-boot restore

The device showed V12R68 `energy_step` active but `/sys/kernel/mm/lru_gen/enabled=0` after boot. The V12R67 60-second early boot guard reported no matches. On a One UI port, `/system/bin/init.mglru.sh` may disable MGLRU based on rounded total RAM.

`scripts/alice-v12r69-mglru-postboot.sh` is **opt-in**, not installed by CI/kernel build. To install, transfer to /data/adb/service.d/99-alice-mglru-restore.sh and chmod 0755, after checking the ROM script. It waits for boot_completed then 15 seconds, checks actual script reference, restores MGLRU at most once, logs the result, and never runs a polling loop. Manually disabling MGLRU later still works.

This is a workaround for a verified ROM policy path, not a fix for SystemUI stalls, LMKD, watchdog or kernel panic. If app switching/reboot worsens with MGLRU enabled, uninstall service and reboot to return to ROM behavior.

No universal fix for crashes/LMKD has been established without synchronized evidence; do not assert stability from host-side tests alone.
