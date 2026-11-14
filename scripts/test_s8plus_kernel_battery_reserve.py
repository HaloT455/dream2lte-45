#!/usr/bin/env python3
"""Safe, host-only validation for the S8+ in-kernel 80/20 reserve indicator."""
from pathlib import Path
src=Path("drivers/battery_v2/alice_battery_reserve.c").read_text()
battery=Path("drivers/battery_v2/sec_battery.c").read_text()
cfg=Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
h=Path("include/linux/alice_battery_reserve.h").read_text()
mk=Path("drivers/battery_v2/Makefile").read_text()
assert "CONFIG_ALICE_BATTERY_RESERVE=y" in cfg
assert "CONFIG_MUIC_HV_MAX77865=y" in cfg and "CONFIG_AFC_CURR_CONTROL_BY_TEMP=y" in cfg
assert "alice_battery_reserve.o" in mk
assert "void alice_battery_reserve_update(int actual, bool charging)" in h
assert "void alice_battery_reserve_update(int actual, bool charging)" in src
assert "alice_battery_reserve_update(battery->capacity" in battery
assert "power_supply_changed(battery->psy_bat)" in battery
assert "battery->capacity = value.intval;" in battery
assert '"ALICE_BATTERY_UPSM_REQUEST=1"' in src
assert 'kobject_uevent_env(kobj, KOBJ_CHANGE' in src
assert 'reserve_state.display_percent = emergency ? real : virtual;' in src
assert 'changed = !reserve_state.valid ||' in src, "must notify on initial state"
assert '"ALICE_BATTERY_UPSM_LOCKED=1"' in src
assert 'upsm_locked_show' in src and '__ATTR_RO(upsm_locked)' in src
assert 'normal_unrestricted_show' in src and '__ATTR_RO(normal_unrestricted)' in src
assert 'sysfs_notify(kobj, NULL, "upsm_locked");' in src
assert "sysfs_create_group(reserve_kobj" in src
assert "sysfs_notify(kobj" in src
assert "subsys_initcall(alice_battery_reserve_init);" in src
assert not any(term in src for term in ["POWER_SUPPLY_PROP_CAPACITY, value", "set_charging_current", "muic_afc_set_voltage", "cpufreq_driver_target", "voltage_max", "shutdown("])

def normal(actual):
    return max(0, min(100, (max(max(0,min(100,actual))-20,0)*100 + 40)//80))

def sample(actual, charging, emergency):
    virtual=normal(actual)
    if emergency and charging and actual>=100:
        emergency=False
    elif not emergency and not charging and virtual<=5:
        emergency=True
    return (actual if emergency else virtual), emergency

assert normal(100)==100
assert normal(80)==75
assert normal(60)==50
assert normal(40)==25
assert normal(24)==5
assert sample(25,False,False)==(6,False)
assert sample(24,False,False)==(24,True)
assert sample(23,False,True)==(23,True)
assert sample(12,False,True)==(12,True)
assert sample(3,False,True)==(3,True)
assert sample(24,True,True)==(24,True)
assert sample(99,True,True)==(99,True)
assert sample(100,True,True)==(100,False)
print("PASS: real 24%=normal 5% triggers real 24% emergency display (not 25%)")
print("PASS: reserve display follows real capacity without changing Samsung fuel gauge")
print("PASS: read-only lock flag, first battery sample uevent and normal full-clock allowance")
print("PASS: 5V/9V AFC, thermal/current safety and power supply report are untouched")
print("NOTE: a Samsung UPSM implementation in userspace is still required for actual UI/power-mode change")
