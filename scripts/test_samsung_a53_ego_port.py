#!/usr/bin/env python3
"""Executable Samsung A53 EGO/energy_table donor-port regression (host C).

The Samsung GPLv2 donor is archived verbatim, and the active Linux 4.4
adapter is compiled and exercised here.  This is not a device/thermal test.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EGO = (ROOT / "research/samsung-a53-exynos1280-ego-reference.c").read_text()
ET = (ROOT / "research/samsung-a53-exynos1280-energy-table-reference.c").read_text()
MODEL = (ROOT / "kernel/sched/energy_aware_model.h").read_text()
PORT = (ROOT / "kernel/sched/energy_aware_samsung_et.h").read_text()
GOV = (ROOT / "kernel/sched/cpufreq_energy_aware.c").read_text()

for source, funcs in (
    (EGO, ("ego_compute_energy(", "ego_find_energy_freq(",
           "ego_map_util_freq(", "ego_compute_cpu_idle_ratio(")),
    (ET, ("et_freq_to_cap(", "et_fill_energy_state(",
          "et_compute_cpu_energy(", "__compute_cpu_energy(")),
):
    for func in funcs:
        assert func in source, ("missing donor function", func)

for needle in (
    "et_compute_cpu_energy_8895(model, index, work)",
    '#include "energy_aware_samsung_et.h"',
    "ego_map_util_freq_8895",
    "state->frequency < work->org_freq",
):
    assert needle in MODEL, needle
for needle in (
    "work.org_freq = ego_map_util_freq_8895(",
    "choice = ego_find_energy_freq(&ea->model, &work, low, high)",
):
    assert needle in GOV, needle
for needle in ("et_freq_to_cap_8895(", "et_cap_to_state_8895(",
               "et_compute_cpu_energy_8895("):
    assert needle in PORT, needle

SOURCE = r'''
#include <assert.h>
#include <stdint.h>
#include "energy_aware_model.h"

int main(void)
{
    struct eagov_energy_state steps[] = {
        {100, 100, 100, 0},
        {200, 200, 250, 0},
        {300, 300, 900, 0},
    };
    struct eagov_energy_model model = {steps, 3, 10, 0, 0};
    struct ego_cpu_work cpus[] = {{80, 512}};
    struct ego_workload work = {cpus, 1, 80, 0};
    struct eagov_energy_choice choice;

    /* Exact translation of the Samsung energy_table frequency index rule. */
    assert(et_freq_to_cap_8895(&model, 100) == 100);
    assert(et_freq_to_cap_8895(&model, 150) == 200);
    assert(et_freq_to_cap_8895(&model, 300) == 300);
    assert(et_freq_to_cap_8895(&model, 400) == 0);
    assert(et_cap_to_state_8895(&model, 101) == 1);
    assert(et_cap_to_state_8895(&model, 301) == EAGOV_NO_STATE);

    /* Real busy + idle accounting: 80*100 + 10*(20*512/1024) = 8100. */
    assert(et_compute_cpu_energy_8895(&model, 0, &work) == 8100);
    assert(ego_compute_energy(&model, 0, &work) == 8100 * 1024ULL / 100ULL);

    /* Original Samsung EGO scan chooses minimum-energy eligible OPP. */
    choice = ego_find_energy_freq(&model, &work, 100, 300);
    assert(choice.state == 0);

    /* Original Samsung ego_map_util_freq: margin is a WORKLOAD FLOOR only.
     * For 80/300 util with 100% margin: 300*2*80/300 = 160 kHz. */
    work.org_freq = ego_map_util_freq_8895(80, 300, 300, 100);
    assert(work.org_freq == 160);
    choice = ego_find_energy_freq(&model, &work, 100, 300);
    assert(choice.state == 1);

    /* A thermal/QoS cap below org_freq wins; never ask for an OC above it. */
    choice = ego_find_energy_freq(&model, &work, 100, 100);
    assert(choice.state == 0);

    /* 25% is the donor's default PELT margin; overflow is avoided. */
    assert(ego_map_util_freq_8895(1024, 2704000, 1196, 25) > 2704000);
    assert(ego_map_util_freq_8895(100, 2704000, 0, 25) == 0);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="samsung-ego-port-") as tmp:
    cpath = Path(tmp) / "test.c"
    exe = Path(tmp) / "test"
    cpath.write_text(SOURCE)
    subprocess.run([os.getenv("HOSTCC", "cc"), "-std=gnu11",
                    "-O2", "-Wall", "-Wextra", "-Werror",
                    "-iquote" + str(ROOT / "kernel/sched"),
                    str(cpath), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("PASS: Samsung A53 donor ET and EGO algorithm paths are compiled and tested")
