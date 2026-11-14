#!/usr/bin/env python3
"""No-touch AFC safety/regression checks for S8+ Exynos8895.
Inspect source and config only: runtime negotiation requires real charger tests.
"""
from pathlib import Path

cfg=Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
hv=Path("drivers/muic/universal/muic_hv_max77865.c").read_text()
bat=Path("drivers/battery_v2/sec_battery.c").read_text()
charger=Path("drivers/battery_v2/max77865_charger.c").read_text()

must = (
"CONFIG_USE_MUIC=y",
"CONFIG_MUIC_UNIVERSAL_MAX77865=y",
"CONFIG_MUIC_HV=y",
"CONFIG_MUIC_HV_MAX77865=y",
"# CONFIG_MUIC_HV_12V is not set",
"CONFIG_AFC_CHARGER_MODE=y",
"CONFIG_AFC_CURR_CONTROL_BY_TEMP=y",
"CONFIG_CHARGER_MAX77865=y",
"CONFIG_FUELGAUGE_MAX77865=y",
)
for item in must:
    assert item in cfg, item
for item in ("ATTACHED_DEV_AFC_CHARGER_5V_MUIC", "ATTACHED_DEV_AFC_CHARGER_9V_MUIC",
             "FUNC_PREPARE_DUPLI_TO_AFC_9V", "FUNC_AFC_9V_TO_AFC_5V"):
    assert item in hv, item
assert "sec_bat_check_afc_temp" in bat
assert "muic_afc_set_voltage(SEC_INPUT_VOLTAGE_5V)" in bat
assert "muic_afc_set_voltage(SEC_INPUT_VOLTAGE_9V)" in bat
assert "POWER_SUPPLY_HEALTH_OVERVOLTAGE" in charger
assert "POWER_SUPPLY_HEALTH_UNDERVOLTAGE" in charger
assert "max77865_set_input_current" in charger
assert "max77865_set_charge_current" in charger
print("PASS: MAX77865 AFC 5V/9V path, battery temperature current control, charge protection remain enabled")
print("NOTE: Does not prove actual fast charging with a charger/cable, firmware, ROM or aged battery")
