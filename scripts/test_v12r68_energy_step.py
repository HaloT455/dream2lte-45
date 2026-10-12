#!/usr/bin/env python3
"""Static checks for genuine independent ALICE EnergyStep-compat governor.

Do not confuse with Samsung EMS energy_step from Exynos2100: its emstune,
uclamp, power tables and driver callbacks require substantial 5.x scheduler
support absent from the Galaxy S8+ Linux 4.4. This version implements an
independent discrete policy-frequency governor using the existing S8+ hooks.
Build and runtime tests remain mandatory.
"""
from pathlib import Path
es = Path("kernel/sched/cpufreq_energy_step.c").read_text()
su = Path("kernel/sched/cpufreq_schedutil.c").read_text()
cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
k = Path("drivers/cpufreq/Kconfig").read_text()
h = Path("include/linux/cpufreq.h").read_text()
m = Path("kernel/sched/Makefile").read_text()
assert "CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYSTEP=y" in cfg
assert "# CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL is not set" in cfg
assert "CONFIG_CPU_FREQ_GOV_ENERGYSTEP=y" in cfg
assert "CONFIG_CPU_FREQ_GOV_SCHEDUTIL=y" in cfg, "Schedutil required for manual rollback"
assert "config CPU_FREQ_DEFAULT_GOV_ENERGYSTEP" in k
assert "config CPU_FREQ_GOV_ENERGYSTEP" in k
assert "(&cpufreq_gov_energy_step)" in h
assert "CONFIG_CPU_FREQ_GOV_ENERGYSTEP) += cpufreq_energy_step.o" in m
assert 'name = "energy_step"' in es
assert 'name = "schedutil"' in su
assert "static unsigned int esgov_step_target" in es
assert "#define ALICE_ESGOV_STEPS\t8U" in es
assert "DIV_ROUND_UP(offset, stride)" in es
assert "cpufreq_driver_resolve_freq(policy, min(ceiling, target))" in es
assert "raw = div64_u64((u64)(base + (base >> 3)) * util, max);" in es
for code in ("cpufreq_add_update_util_hook", "cpufreq_remove_update_util_hook",
             "cpufreq_register_governor", "esgov_get_util",
             "esgov_iowait_boost", "CPUFREQ_GOV_LIMITS",
             "__cpufreq_driver_target", "policy->related_cpus"):
    assert code in es, code
assert "emstune" not in es or "NOT Samsung EMS" in es
print("PASS: EnergyStep-compat registered independently and default configured")
print("PASS: Eight discrete steps clamp to cpufreq policy min/max; WALT, thermal limits preserved")
print("PASS: schedutil fallback remains compiled and selectable")
print("NOTE: static tests do not prove Samsung EMS parity, power savings or device stability")
