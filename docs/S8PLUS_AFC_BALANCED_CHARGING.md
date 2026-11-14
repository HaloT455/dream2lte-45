# Galaxy S8+ — AFC + Balanced Battery support and safe verification

## Target
Samsung Galaxy S8+ Exynos 8895 (SM-G955F, dream2lte), existing charger/firmware path with MAX77865 MUIC and charger controller.

## Supported baseline (already in the S8+ kernel)
- CONFIG_MUIC_UNIVERSAL_MAX77865=y
- CONFIG_MUIC_HV=y
- CONFIG_MUIC_HV_MAX77865=y
- CONFIG_AFC_CHARGER_MODE=y
- CONFIG_AFC_CURR_CONTROL_BY_TEMP=y
- CONFIG_CHARGER_MAX77865=y, CONFIG_FUELGAUGE_MAX77865=y
- 5V and 9V Adaptive Fast Charging state transitions in drivers/muic/universal/muic_hv_max77865.c.
- 12V HV mode disabled; charger current limits and temperature protection untouched.

S8/S8+ supports Samsung Adaptive Fast Charging, nominally up to about 15W (commonly 9V/1.67A) with a compatible charger and cable, *not* 25W PPS superfast charging. 5V operation is the safe compatibility fallback. An adapter rated above 15W does not compel 15W or higher charging on this device.

**This branch does not force 9V, bypass negotiated AFC, raise input current or voltage, lower battery-temperature protection or modify Samsung battery charging profiles.** It only checks that the existing support stays present while changing CPUFreq policy. Some Android ports may disable fast cable charging or override it in userspace; a successful kernel compile cannot verify negotiation.

## Check on the real S8+ with a genuine compatible AFC adapter
```sh
adb push scripts/collect_s8plus_afc.sh /data/local/tmp/s8plus-afc.sh
adb shell sh /data/local/tmp/s8plus-afc.sh > s8plus-afc-readonly.txt
```

Compare unplugged, cable plugged screen off, and charging while a game renders. The last case may throttle charging to avoid excessive battery temperature. Respect the charger USB port, avoid using damaged batteries, and do not force 9V through sysfs or modify MUIC register values.

Use a known-good boot image for repacking and keep a backup. CI compilation, static test and DTB match do not prove successful boot, battery health or safe charging under stress.
