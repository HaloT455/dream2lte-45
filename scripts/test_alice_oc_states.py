#!/usr/bin/env python3
"""Host regression checks for Exynos8895 overclock Energy-Aware states.

CAL/ASV OPP validity and voltage are checked at runtime by eagov_build_model().
These host tests only verify arithmetic and the committed board/source limits.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOC = (ROOT / "arch/arm64/boot/dts/exynos/exynos8895.dtsi").read_text()
BOARD = (ROOT / "arch/arm64/boot/dts/exynos/exynos8895-dream2lte_common.dtsi").read_text()
GOV = (ROOT / "kernel/sched/cpufreq_energy_aware.c").read_text()
ACME = (ROOT / "drivers/cpufreq/exynos-acme.c").read_text()

assert "max-freq = <2002000>;" in BOARD
assert "max-freq = <2704000>;" in BOARD
assert "frequency-data = <455000 598000 715000" in SOC
assert "frequency-data = <741000 858000 962000" in SOC
assert "dev_pm_opp_find_freq_exact" in GOV
assert "dev_pm_opp_get_voltage" in GOV
assert "eagov_append_oc_states" in GOV
assert '"OC_EST"' in GOV and '"DTS"' in GOV
assert "cal_dfs_get_rate_table" in ACME
assert "cal_dfs_get_asv_table" in ACME
assert "dev_pm_opp_add(" in ACME

SOURCE = r'''
#include <stdint.h>
#include <assert.h>
typedef unsigned long long u64;
static inline unsigned long long div64_u64(unsigned long long a, unsigned long long b)
{
    return a / b;
}
#include "energy_aware_oc.h"
int main(void)
{
    unsigned int a53, m2, p53, pm2;
    a53 = eagov_estimate_oc_capacity(305U, 1690000U, 2002000U);
    m2 = eagov_estimate_oc_capacity(1024U, 2314000U, 2704000U);
    assert(a53 == 361U);
    assert(m2 > 1024U && m2 < 1300U);
    assert(eagov_estimate_oc_capacity(1024U, 2314000U, 2200000U) == 0U);
    assert(eagov_estimate_oc_capacity(1024U, 0U, 2704000U) == 0U);
    p53 = eagov_estimate_oc_power(139U, 1690000U, 1000000U,
                                  2002000U, 1100000U);
    pm2 = eagov_estimate_oc_power(1469U, 2314000U, 1100000U,
                                  2704000U, 1200000U);
    assert(p53 > 139U && pm2 > 1469U);
    assert(eagov_estimate_oc_power(139U, 1690000U, 0U,
                                   2002000U, 1100000U) == 0U);
    assert(eagov_estimate_oc_power(139U, 1690000U, 1000000U,
                                   2002000U, 0U) == 0U);
    assert(eagov_estimate_oc_power(139U, 1690000U, 1000000U,
                                   2002000U, 1300000U) > p53);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    cfile = Path(d) / "oc_test.c"
    binary = Path(d) / "oc_test"
    cfile.write_text(SOURCE)
    subprocess.run(["cc", "-std=c99", "-O2", "-Wall", "-Wextra",
                    "-Werror", "-I" + str(ROOT / "kernel/sched"),
                    str(cfile), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("PASS: real CAL/ASV OC interface and voltage/capacity estimates")
