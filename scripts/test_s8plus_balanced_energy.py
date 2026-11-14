#!/usr/bin/env python3
"""Host checks: S8+ sustained-efficiency Energy Step against the prior profile.

Does not estimate real-world battery life, FPS or surface temperature.
"""
from pathlib import Path

src = Path("kernel/sched/cpufreq_energy_step.c").read_text()
cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
assert "static unsigned int esgov_reverse_energy_target" in src
assert "if (util < max - max / 4)" in src
assert "base + (base >> 4)" in src
assert "headroom_op = esgov_step_target(policy, headroom_raw);" in src
assert "previous >= minimum_op && previous <= headroom_op" in src
assert "ESGOV_DEFAULT_UP_RATE_LIMIT_US\t\t(3000)" in src
assert "ESGOV_DEFAULT_DOWN_RATE_LIMIT_US\t(12000)" in src
assert "CONFIG_ZRAM_DEF_COMP_LZ4KD=y" in cfg
assert "# CONFIG_MALI_HALO_NPU_PARTITION is not set" in cfg
assert "CONFIG_EXYNOS_VPU_HARDWARE=y" in cfg
assert "CONFIG_PSI=y" in cfg
assert "# CONFIG_ANDROID_LOW_MEMORY_KILLER is not set" in cfg

def step(lo, hi, requested):
    stride = max(1, (hi - lo + 7) // 8)
    offset = max(0, min(requested, hi) - lo)
    return min(hi, lo + ((offset + stride - 1) // stride) * stride)

def target(lo, hi, cpu, u, cap, older=None, balanced=True):
    """Mirrors the governor policy math before driver OPP resolution."""
    required = step(lo, hi, hi * u // cap)
    burst = step(lo, hi, (hi + hi // 8) * u // cap)
    moderate = step(lo, hi, (hi + hi // 16) * u // cap)
    head = moderate if balanced and u < cap - cap // 4 else burst
    if u <= cap // 6 or cpu >= 4 and u <= cap // 4:
        return required
    if u < cap - cap // 4 and older is not None and required <= older <= head:
        return older
    return head

for cpu, floor, ceiling in ((0, 455000, 2002000), (4, 741000, 2704000)):
    saved = 0
    for util in range(0, 1025):
        old = target(floor, ceiling, cpu, util, 1024, balanced=False)
        new = target(floor, ceiling, cpu, util, 1024)
        assert floor <= new <= ceiling
        if util < 768:
            assert new <= old, (cpu, util, new, old)
            saved += new < old
        else:
            assert new == old, (cpu, util, new, old)
    assert saved > 10, (cpu, saved)
    for util in (800, 900, 1024):
        assert target(floor, ceiling, cpu, util, 1024) == target(floor, ceiling, cpu, util, 1024, balanced=False)
    print(f"PASS: CPU{cpu} reduces requested moderate-load OPP at {saved} util samples, high-load unchanged")

print("PASS: no thermal or voltage adjustments; GPU full, VPU native, PSI LMKD, LZ4KD retained")
print("NOTE: CPUFreq driver OPP tables, frame pacing, current, and battery require phone measurements")
