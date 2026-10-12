#!/usr/bin/env python3
from pathlib import Path
s=Path("kernel/sched/cpufreq_energy_step.c").read_text()
w=s.split("static void esgov_work(",1)[1].split("static void esgov_irq_work(",1)[0]
assert "mutex_lock(&sg_policy->work_lock);" in w
assert "for (;;)" not in w, "Unbounded worker frequency replay prohibited"
assert w.count("__cpufreq_driver_target(") == 1
assert "raw_spin_lock_irqsave(&sg_policy->update_lock, flags);" in w
assert "raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);" in w
assert "sg_policy->work_in_progress = false;" in w
assert w.index("raw_spin_unlock_irqrestore") < w.index("__cpufreq_driver_target(")
print("PASS: bounded Energy Step worker and no spinlock held during cpufreq target")
