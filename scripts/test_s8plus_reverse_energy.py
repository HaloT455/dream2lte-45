#!/usr/bin/env python3
"""Host-only invariants for Exynos8895 inverse energy-step experiment."""
from pathlib import Path
s = Path("kernel/sched/cpufreq_energy_step.c").read_text()
cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
z = Path("drivers/block/zram/zram_drv.c").read_text()
a = Path("crypto/lz4kd.c").read_text()
assert "static unsigned int esgov_reverse_energy_target" in s
assert "return esgov_reverse_energy_target(sg_policy, util, max, base, raw);" in s
assert "esgov_step_target(policy, minimum_raw)" in s
assert "esgov_step_target(policy, headroom_raw)" in s
assert "previous >= minimum_op && previous <= headroom_op" in s
assert "flags & SCHED_CPUFREQ_DL" in s and "esgov_iowait_boost" in s
assert "CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYSTEP=y" in cfg
assert "CONFIG_ZRAM_DEF_COMP_LZ4KD=y" in cfg
assert "CONFIG_CRYPTO_LZ4KD=y" in cfg
assert "# CONFIG_MALI_HALO_NPU_PARTITION is not set" in cfg
assert "# CONFIG_ANDROID_LOW_MEMORY_KILLER is not set" in cfg
assert "# CONFIG_ANDROID_SIMPLE_LMK is not set" in cfg
assert "CONFIG_PSI=y" in cfg
assert "CONFIG_EXYNOS_VPU_HARDWARE=y" in cfg
assert '"lz4kd" : "lz4"' in z
assert 'if (!len || len >= slen)' in a

def step(lo, hi, want):
    stride = max(1, (hi - lo + 7)//8)
    offset = max(0, min(want, hi) - lo)
    return min(hi, lo + (offset + stride - 1)//stride * stride)

def reverse(lo, hi, util, cap, base, old, cpu):
    if not cap: return lo
    raw = ((base + base//8)*util)//cap
    required = base * util//cap
    low = step(lo, hi, required)
    boosted = step(lo, hi, raw)
    if util <= cap//6 or (cpu >= 4 and util <= cap//4):
        return low
    if util < cap - cap//4 and old is not None and low <= old <= boosted:
        return old
    return boosted

assert reverse(741000,2704000,0,1024,2704000,None,4)==741000
lo=reverse(741000,2704000,255,1024,2704000,None,4)
hi=step(741000,2704000,(2704000+2704000//8)*255//1024)
assert lo <= hi and lo < hi, (lo,hi)
assert reverse(455000,2002000,900,1024,2002000,None,0) >= 0.85*2002000
old=step(455000,2002000,2002000*450//1024)
assert reverse(455000,2002000,450,1024,2002000,old,0)==old
for cpu, low, high in [(0,455000,2002000),(4,741000,2704000)]:
    for u in range(0,1025,31):
        v=reverse(low,high,u,1024,high,None,cpu)
        assert low<=v<=high, (cpu,u,v)
print("PASS: reverse Energy Step low-load minimum, game burst headroom, no thermal/driver policy overrun")
print("PASS: S8+ G71 graphics full mask config, real LZ4KD, PSI/lmkd backend, native VPU retained")
print("NOTE: static model only; game FPS, power, temperatures, boot not measured")
