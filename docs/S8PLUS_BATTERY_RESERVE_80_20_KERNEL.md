# S8+ ALice kernel battery reserve 80/20 (read-only indicator)

Device: Galaxy S8+ Exynos 8895 (dream2lte).

**At 24% real battery while discharging**, the virtual normal percentage is 5%, and the kernel switches to emergency mode whose display percentage is **24% real**, *not 25%*. Emergency state remains until the battery reaches real 100% while charging, preventing oscillations near the threshold.

| Real battery | Normal virtual | Kernel display |
| ---: | ---: | --- |
| 100 | 100 | 100 normal |
| 80 | 75 | 75 normal |
| 60 | 50 | 50 normal |
| 40 | 25 | 25 normal |
| 25 | 6 | 6 normal |
| **24** | **5** | **24 emergency** |
| 23 | 4 | 23 emergency |
| 20 | 0 | 20 emergency |
| 5 | 0 | 5 emergency |

`CONFIG_ALICE_BATTERY_RESERVE=y` integrates with Samsung battery_v2 monitoring without an extra polling thread, through `drivers/battery_v2/alice_battery_reserve.c`.

Read-only sysfs `/sys/kernel/alice_battery_reserve/`: `real_percent`, `normal_percent`, `display_percent`, `emergency_active`, `upsm_requested`, `actual_charging`. At state transitions, the kernel emits `KOBJ_CHANGE` with `ALICE_BATTERY_UPSM_REQUEST=1` to be consumed by the ROM.

**Android/One UI limitation:** The kernel-only integration does **not** change the status-bar percentage or launch Samsung's proprietary Ultra Power Saving Mode. A trusted vendor/system companion must listen to the event and integrate with Samsung's proprietary API. `upsm_requested=1` is a request, not a claim that Samsung UPSM is enabled.

**Safety:** Real battery capacity under `/sys/class/power_supply/battery/capacity` remains unchanged for IC, Android BatteryService, AFC, thermal cutoff and low-battery shutdown. This is a presentation/reserve policy, not real physical capacity isolation or added battery energy. Preserves Balanced Energy Step, full GPU Mali-G71 MP20, VPU, ZRAM LZ4KD, PSI-LMKD and 5V/9V Adaptive Fast Charging.

Check on real S8+:

```sh
adb shell 'for p in real_percent normal_percent display_percent emergency_active upsm_requested actual_charging; do echo -n "$p: "; cat "/sys/kernel/alice_battery_reserve/$p"; done'
adb shell cat /sys/class/power_supply/battery/capacity
```

Requires matching boot/ramdisk and device verification before daily use.
