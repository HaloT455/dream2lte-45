#!/usr/bin/env python3
from pathlib import Path
s = Path("kernel/sched/cpufreq_energy_step.c").read_text()
w = s.split("static void esgov_work(", 1)[1].split("static void esgov_irq_work(", 1)[0]
assert "attempt < 2" in w, "worker replay must be bounded"
assert "for (;;)" not in w
assert "irq_work_queue(&sg_policy->irq_work);" in w
assert "if (sg_policy->next_freq == freq)" in w
assert "sg_policy->work_in_progress = false;" in w
assert w.index("__cpufreq_driver_target") < w.index("sg_policy->work_in_progress = false")
assert "mutex_lock(&sg_policy->work_lock);" in w
assert "raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);" in w
print("PASS: bounded Energy Step replay, follow-up queue, and no early busy clear")
