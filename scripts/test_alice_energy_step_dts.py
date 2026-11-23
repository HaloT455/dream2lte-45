#!/usr/bin/env python3
"""Run the actual C energy selector against DTS data and a rational energy oracle.

Host tests cover selection, limits and accounting; they do not test device boot.
"""
import ctypes as C
from fractions import Fraction
from pathlib import Path
import os
import random
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DTS = ROOT / "arch/arm64/boot/dts/exynos/exynos8895.dtsi"


def values(label, prop):
    text = DTS.read_text()
    node = re.search(r"\b" + label + r":\s*[^{}]+\{([^{}]+)\}", text, re.S)
    if not node:
        raise AssertionError("Missing DTS node: " + label)
    match = re.search(r"\b" + prop + r"\s*=\s*<([^>]+)>", node[1], re.S)
    if not match:
        raise AssertionError("Missing DTS property: " + prop)
    return [int(v) for v in re.findall(r"\d+", match[1])]


class State(C.Structure):
    _fields_ = [(name, C.c_uint) for name in
                ("frequency", "capacity", "core_power", "cluster_power")]


class Model(C.Structure):
    _fields_ = [("states", C.POINTER(State)), ("nr_states", C.c_uint),
                ("core_idle", C.c_uint), ("core_pwroff", C.c_uint),
                ("cluster_idle", C.c_uint)]


def cluster_model(core_label, cluster_label):
    frequencies = values(core_label, "frequency-data")
    core = values(core_label, "busy-cost-data")
    cluster = values(cluster_label, "busy-cost-data")
    assert len(core) == len(cluster) == 2 * len(frequencies)
    assert core[::2] == cluster[::2]
    rows = [(freq, core[2*i], core[2*i+1], cluster[2*i+1])
            for i, freq in enumerate(frequencies)]
    return rows, values(core_label, "idle-cost-data")[0], \
        values(cluster_label, "idle-cost-data")[0]


class CPUWork(C.Structure):
    _fields_ = [("util", C.c_uint), ("clkoff_ratio", C.c_uint)]


class IdleHistory(C.Structure):
    _fields_ = [("clkoff", C.c_ulonglong * 8), ("pwroff", C.c_ulonglong * 8),
                ("clkoff_sum", C.c_ulonglong), ("pwroff_sum", C.c_ulonglong),
                ("period_start", C.c_ulonglong), ("last_update", C.c_ulonglong),
                ("index", C.c_uint), ("state", C.c_int), ("initialized", C.c_int)]


def distribute(peak, total, cpus):
    work = []
    for _ in range(cpus):
        util = min(peak, total)
        work.append(util)
        total -= util
    return work


def reference_energy(row, peak, total, cpus, core_idle, cluster_idle,
                     ratios=None, core_pwroff=0):
    """A53 normalized active/CLKOFF/PWROFF times, plus S8 shared power."""
    _, cap, core_power, cluster_power = row
    ratios = [1024] * cpus if ratios is None else ratios
    numerator = 0
    for util, ratio in zip(distribute(peak, total, cpus), ratios):
        active = min(util, cap)
        idle = cap - active
        clkoff = idle * min(ratio, 1024) // 1024
        numerator += core_power * active + core_idle * clkoff
        numerator += core_pwroff * (idle - clkoff)
    shared_active = min(Fraction(peak, cap), 1)
    return int((Fraction(numerator, cap) + cluster_power * shared_active
                + cluster_idle * (1 - shared_active)) * 1024)


class TestEnergySteps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        source = Path(cls.tmp.name) / "selector.c"
        shared = Path(cls.tmp.name) / "selector.so"
        source.write_text('''#include "energy_aware_model.h"
#include "energy_aware_idle.h"
unsigned int select_state(const struct eagov_energy_model *model,
    struct ego_cpu_work *cpus, unsigned int count,
    unsigned int min, unsigned int max, unsigned long long *energy)
{
    struct ego_workload work = { cpus, count, 0 };
    unsigned int i;
    for (i = 0; i < count; i++)
        if (cpus[i].util > work.peak) work.peak = cpus[i].util;
    struct eagov_energy_choice choice =
        ego_find_energy_freq(model, &work, min, max);
    *energy = choice.energy;
    return choice.state;
}
void idle_event(struct ego_idle_history *idle, unsigned long long now, int state)
{
    ego_idle_update(idle, now, state);
}
unsigned int idle_ratio(const struct ego_idle_history *idle)
{
    return ego_idle_clkoff_ratio(idle);
}
''')
        subprocess.run([os.environ.get("HOSTCC", "cc"), "-std=c99", "-O2",
                        "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                        "-iquote" + str(ROOT / "kernel/sched"), str(source),
                        "-o", str(shared)], check=True)
        cls.lib = C.CDLL(str(shared))
        cls.lib.select_state.argtypes = [C.POINTER(Model), C.POINTER(CPUWork)] + [C.c_uint] * 3 + [C.POINTER(C.c_ulonglong)]
        cls.lib.idle_event.argtypes = [C.POINTER(IdleHistory), C.c_ulonglong, C.c_int]
        cls.lib.idle_ratio.argtypes = [C.POINTER(IdleHistory)]
        cls.lib.idle_ratio.restype = C.c_uint
        cls.lib.select_state.restype = C.c_uint

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def select(self, rows, core_idle, cluster_idle, peak, total, cpus=4,
               min_freq=0, max_freq=2**32-1, ratios=None, core_pwroff=0):
        array = (State * len(rows))(*(State(*row) for row in rows))
        model = Model(array, len(rows), core_idle, core_pwroff, cluster_idle)
        ratios = [1024] * cpus if ratios is None else ratios
        work = (CPUWork * cpus)(*(CPUWork(u, r) for u, r in
                                   zip(distribute(peak, total, cpus), ratios)))
        energy = C.c_ulonglong()
        index = self.lib.select_state(C.byref(model), work, cpus,
                                     min_freq, max_freq, C.byref(energy))
        return index, energy.value

    def test_explicit_dts_frequency_bindings(self):
        expected = [
            ("CPU_COST_1", "CLUSTER_COST_1", 9, 455000, 1690000, 122, 605),
            ("CPU_COST_0", "CLUSTER_COST_0", 13, 741000, 2314000, 643, 6050),
        ]
        for core, cluster, nr, low, high, pmin, pmax in expected:
            rows, _, _ = cluster_model(core, cluster)
            self.assertEqual(len(rows), nr)
            self.assertEqual((rows[0][0], rows[-1][0]), (low, high))
            self.assertEqual([r[0] for r in rows], sorted(set(r[0] for r in rows)))
            self.assertEqual([r[1] for r in rows], sorted(set(r[1] for r in rows)))
            self.assertEqual(4 * rows[0][2] + rows[0][3], pmin)
            self.assertEqual(4 * rows[-1][2] + rows[-1][3], pmax)

    def test_c_selector_matches_energy_oracle(self):
        rng = random.Random(8895)
        for labels in (("CPU_COST_1", "CLUSTER_COST_1"), ("CPU_COST_0", "CLUSTER_COST_0")):
            rows, ci, si = cluster_model(*labels)
            for _ in range(1200):
                cpus = rng.randint(1, 4)
                peak = rng.randint(0, rows[-1][1])
                total = rng.randint(peak, peak * cpus)
                lo = rng.randrange(len(rows))
                hi = rng.randint(lo, len(rows)-1)
                ratios = [rng.randint(0, 1024) for _ in range(cpus)]
                result, energy = self.select(rows, ci, si, peak, total, cpus,
                                             rows[lo][0], rows[hi][0], ratios)
                feasible = [i for i in range(lo, hi+1) if rows[i][1] * 8 >= peak * 9]
                expected = min(feasible, key=lambda i: (
                    reference_energy(rows[i], peak, total, cpus, ci, si, ratios), rows[i][0])) if feasible else hi
                self.assertEqual(result, expected, (labels, peak, total, lo, hi))
                self.assertEqual(energy, reference_energy(rows[result], peak, total, cpus, ci, si, ratios))

    def test_energy_cost_changes_decision_at_fixed_util(self):
        # Both states can execute the work. Changing power alone changes selection.
        rows = [(100, 128, 100, 10), (200, 256, 110, 10)]
        self.assertEqual(self.select(rows, 0, 0, 64, 64)[0], 1)
        rows[1] = (200, 256, 1000, 10)
        self.assertEqual(self.select(rows, 0, 0, 64, 64)[0], 0)

    def test_idle_saturation_thermal_and_qos(self):
        rows, ci, si = cluster_model("CPU_COST_1", "CLUSTER_COST_1")
        self.assertEqual(self.select(rows, ci, si, 0, 0)[0], 0)
        self.assertEqual(self.select(rows, ci, si, 305, 1220)[0], 8)
        self.assertEqual(self.select(rows, ci, si, 305, 1220,
                                     max_freq=949000)[0], 4)
        self.assertGreaterEqual(rows[self.select(rows, ci, si, 0, 0,
                                                min_freq=1248000)[0]][0], 1248000)
        self.assertEqual(self.select(rows, ci, si, 10, 10, min_freq=2002000)[0], 2**32-1)
        self.assertEqual(self.select(rows, ci, si, 10, 10, cpus=0)[0], 2**32-1)
        self.assertEqual(self.select([], 0, 0, 10, 10)[0], 2**32-1)

    def test_cluster_shared_once_and_idle_above_busy(self):
        # Actual M2 data has shared idle power 50 but first busy power 35.
        rows, ci, si = cluster_model("CPU_COST_0", "CLUSTER_COST_0")
        self.assertGreater(si, rows[0][3])
        _, energy = self.select(rows[:1], ci, si, 100, 100, cpus=4)
        self.assertEqual(energy, reference_energy(rows[0], 100, 100, 4, ci, si))
        # Fully busy: core power per CPU, cluster power exactly once.
        _, energy = self.select(rows[:1], ci, si, 328, 1312, cpus=4)
        self.assertEqual(energy, (4 * 152 + 35) * 1024)

    def test_a53_idle_history_changes_frequency_at_fixed_work(self):
        rows = [(100, 100, 100, 0), (200, 200, 110, 0)]
        # With costly shallow idle, finishing sooner is less attractive.
        shallow = self.select(rows, 100, 0, 50, 50, cpus=1, ratios=[1024])[0]
        deep = self.select(rows, 100, 0, 50, 50, cpus=1, ratios=[0])[0]
        self.assertEqual((shallow, deep), (0, 1))

    def test_a53_eight_period_idle_history(self):
        idle = IdleHistory()
        event = lambda t, state: self.lib.idle_event(C.byref(idle), t, state)
        ratio = lambda: self.lib.idle_ratio(C.byref(idle))
        self.assertEqual(ratio(), 1024)  # conservative unknown history
        event(0, 0)
        event(4_000_000, 1)
        event(8_000_000, -1)
        self.assertEqual((idle.clkoff_sum, idle.pwroff_sum), (4_000_000, 4_000_000))
        self.assertEqual(ratio(), 512)
        event(40_000_000, -1)
        self.assertEqual((idle.clkoff_sum, idle.pwroff_sum), (0, 0))
        self.assertEqual(ratio(), 1024)
        event(40_000_000, 1)
        event(1_000_000_000, -1)
        self.assertEqual(ratio(), 0)
        self.assertLessEqual(idle.pwroff_sum, 32_000_000)
        snapshot = bytes(idle)
        event(900_000_000, 0)
        self.assertEqual(bytes(idle), snapshot)  # backwards clock ignored

    def test_equal_energy_prefers_lowest_frequency(self):
        rows = [(100, 100, 100, 0), (200, 200, 200, 0)]
        self.assertEqual(self.select(rows, 0, 0, 50, 50)[0], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
