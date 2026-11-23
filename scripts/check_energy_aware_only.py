#!/usr/bin/env python3
"""Fail if the target config or linked image includes another CPUFreq governor."""
import argparse
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("config", type=Path)
parser.add_argument("--system-map", type=Path)
args = parser.parse_args()
text = args.config.read_text()
settings = dict(re.findall(r"^CONFIG_(\w+)=(.+)$", text, re.M))
for symbol in ("CPU_FREQ_ENERGY_AWARE_ONLY", "CPU_FREQ_GOV_ENERGYAWARE",
               "CPU_FREQ_DEFAULT_GOV_ENERGYAWARE", "DEFAULT_USE_ENERGY_AWARE"):
    assert settings.get(symbol) == "y", symbol + " must be built in"
for symbol, value in settings.items():
    if symbol.startswith(("CPU_FREQ_GOV_", "CPU_FREQ_DEFAULT_GOV_")):
        assert symbol in ("CPU_FREQ_GOV_ATTR_SET", "CPU_FREQ_GOV_ENERGYAWARE",
                          "CPU_FREQ_DEFAULT_GOV_ENERGYAWARE"), (symbol, value)
assert settings.get("SCHED_HMP") not in ("y", "m")
if args.system_map:
    symbols = {line.split()[-1] for line in args.system_map.read_text().splitlines() if line.split()}
    assert "cpufreq_gov_energy_aware" in symbols
    for gov in ("schedutil", "energy_step", "sched", "performance", "powersave",
                "userspace", "ondemand", "conservative", "interactive", "blu_active"):
        assert "cpufreq_gov_" + gov not in symbols, gov + " governor present"
    for symbol in ("sugov_update_shared", "sugov_update_single", "esgov_update_shared",
                   "esgov_update_single", "cpufreq_performance_init",
                   "cpufreq_governor_performance", "cpufreq_governor_dbs"):
        assert symbol not in symbols, symbol + " present"
print("PASS: energy_aware is the sole CPUFreq governor" +
      (" in config and linked System.map" if args.system_map else " in config"))
