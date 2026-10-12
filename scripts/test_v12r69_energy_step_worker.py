#!/usr/bin/env python3
from pathlib import Path
s=Path("kernel/sched/cpufreq_energy_step.c").read_text()
w=s.split("static void esgov_work(",1)[1].split("static void esgov_irq_work(",1)[0]
assert "mutex_lock(&sg_policy->work_lock);" in w
assert "for (;;)" in w
assert "__cpufreq_driver_target" in w
assert w.index("mutex_lock(&sg_policy->work_lock);") < w.index("__cpufreq_driver_target")
assert w.index("__cpufreq_driver_target") < w.index("sg_policy->work_in_progress = false;")
assert "if (sg_policy->next_freq == freq)" in w
assert "raw_spin_unlock_irqrestore" in w
print("PASS: energy_step worker retains busy state and drains latest target")
