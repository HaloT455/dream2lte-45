# S8+ ALice kernel battery reserve 80/20 (read-only indicator)

Device: Galaxy S8+ Exynos 8895 (dream2lte).

**At 24% real battery while discharging**, the virtual normal percentage is 5%, and the kernel switches to emergency mode whose display percentage is **24% real**, *not 25%*. Emergency state remains until the battery reaches real 100% while plugged in **and the cable is then unplugged**. The full-charge event is latched so a battery gauge drop from 100 to 99 on unplug still releases emergency without oscillation.

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

## Locked emergency policy (requested)

- **Normal virtual 100% through 6%:** kernel reserve monitor does not impose a CPU/GPU frequency limit. Existing Balanced Energy Step still controls CPU DVFS as before; no battery life or FPS improvement is guaranteed without device measurements.
- **Normal virtual reaches 5% at real 24%:** kernel sets `emergency_active=1`, `upsm_requested=1`, **`upsm_locked=1`**, and `display_percent=24` in its read-only interface. A One UI privileged bridge must update SystemUI battery display; the actual fuel-gauge reading is never spoofed.
- While locked, `upsm_locked` is read-only; the ordinary UI cannot clear the *kernel request*. It is maintained during charging even at real 100%, and unlocks only once the cable is unplugged **after a completed 100% charge**. Emergency calls, charging protections, physical power-off and recovery remain functional.
- Optional KernelSU/Magisk `service.sh` companion may re-enable **standard Android Battery Saver** at 15-second intervals if disabled. It does nothing to normal CPU/GPU clocks. The proprietary Samsung **Limit apps and Home screen** mode from the screenshot cannot be forced or its toggle hidden without a ROM-specific privileged One UI integration. In Samsung Settings configure the desired saver options **before** triggering reserve.
- If the guardian prevents the desired phone use, uninstall the module from KernelSU/Magisk or recovery; it is a TEST module.

## 100% full-charge + unplug and kernel-only behavior

- Charge to **100% real**, then unplug: kernel clears emergency mode and the next discharge session starts from the normal virtual 100% scale. Gauge 99% on disconnect is supported by a full-charge latch.
- **No Magisk, KernelSU, daemon or module needed** for in-kernel reserve calculation, state machine, AFC protections, or emergency governor frequency reduction.
- The Energy Step governor (when selected) leaves CPU/GPU policy unchanged in normal virtual mode. On reserve it disables extra CPU headroom and requests <=70% of CPU peak; vendor CPUFreq/thermal constraints remain in effect. The GPU partition and thermal driver are unchanged.
- One UI proprietary UPSM activation, its non-disableable screen, and virtual percentage **on the Samsung status bar** are not capabilities the Linux kernel alone can provide. The kernel exposes a read-only lock/request to Android; achieving the screenshot exactly still requires modifying the ROM's privileged SystemUI/PowerManager components. This is not present in this BOOT/kernel-only output.
- `/sys/kernel/alice_battery_reserve/full_charge_seen` reports whether 100% real has occurred while plugged in during the current emergency cycle.
