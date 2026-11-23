#!/usr/bin/env python3
"""Host-side regression checks for the Exynos8895 DTS-backed energy steps.

These are SOURCE/DTS tests, not a substitute for hardware runtime measurements.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DTS = ROOT / "arch/arm64/boot/dts/exynos/exynos8895.dtsi"
GOV = ROOT / "kernel/sched/cpufreq_energy_aware.c"


def states(label):
    text = DTS.read_text()
    pattern = r"\\b" + re.escape(label) + r":\\s*[^{}]+?\\{\\s*busy-cost-data\\s*=\\s*<([^>]+)>"
    match = re.search(pattern, text, re.S)
    if not match:
        raise AssertionError("Missing Samsung power states for " + label)
    values = [int(v) for v in re.findall(r"\\d+", match.group(1))]
    if not values or len(values) % 2:
        raise AssertionError("Invalid capacity/power pairs for " + label)
    return list(zip(values[::2], values[1::2]))


def step_power(core, cluster, step, cluster_size=4):
    """Match kernel's index -> core + shared cluster busy power."""
    if not step:
        return 0
    cap, core_power = core[min(step, len(core)) - 1]
    shared_power = next((power for state_cap, power in cluster
                         if state_cap >= cap), cluster[-1][1])
    return cluster_size * core_power + shared_power


class TestEnergySteps(unittest.TestCase):
    def test_a53_dts_steps(self):
        core, cluster = states("CPU_COST_1"), states("CLUSTER_COST_1")
        self.assertEqual(len(core), 9)
        self.assertEqual(step_power(core, cluster, 1), 122)
        self.assertEqual(step_power(core, cluster, 3), 163)
        self.assertEqual(step_power(core, cluster, 9), 605)
        self.assertEqual(step_power(core, cluster, 32), 605)
        self.assertEqual(step_power(core, cluster, 0), 0)

    def test_m2_dts_steps(self):
        core, cluster = states("CPU_COST_0"), states("CLUSTER_COST_0")
        self.assertEqual(len(core), 13)
        self.assertEqual(step_power(core, cluster, 1), 643)
        self.assertEqual(step_power(core, cluster, 13), 6050)
        self.assertEqual(step_power(core, cluster, 32), 6050)

    def test_power_envelopes_are_monotonic(self):
        for core_name, cluster_name in (
            ("CPU_COST_1", "CLUSTER_COST_1"),
            ("CPU_COST_0", "CLUSTER_COST_0"),
        ):
            core, cluster = states(core_name), states(cluster_name)
            budgets = [step_power(core, cluster, i)
                       for i in range(1, len(core) + 1)]
            self.assertEqual(budgets, sorted(budgets))
            self.assertTrue(all(v > 0 for v in budgets))

    def test_governor_really_consumes_power_states(self):
        source = GOV.read_text()
        for required in (
            "eagov_dts_step_power(policy, core, cluster, step)",
            "step_power = eagov_dts_step_power",
            "opp_busy_power <= effective_budget",
            "energy < best_energy",
            "core_state->cap",
            "core_state->power",
            "cluster_state->power",
            "energy_step = __ATTR_RW(energy_step)",
            "return found ? best_freq : policy->max",
        ):
            self.assertIn(required, source)
        self.assertNotIn("ALICE_ESGOV_STEPS", source)
        self.assertNotRegex(source, r"policy->max\\s*\\*\\s*util\\s*/")


if __name__ == "__main__":
    unittest.main(verbosity=2)
