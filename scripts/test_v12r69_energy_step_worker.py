#!/usr/bin/env python3
from pathlib import Path
s = Path("kernel/sched/cpufreq_energy_step.c").read_text()
w = s.split("static void esgov_work(", 1)[1].split("static void esgov_irq_work(", 1)[0]
assert "attempt < 2" in w, "worker replay must be bounded"
assert "for (;;)" not in w
assert "irq_work_queue(&sg_policy->irq_work);" not in w
assert "queue_kthread_work(&sg_policy->worker, &sg_policy->work);" in w
assert "if (sg_policy->stopping || sg_policy->next_freq == freq)" in w
assert "sg_policy->work_in_progress = false;" in w
after_target = w.split("__cpufreq_driver_target", 1)[1]
assert "sg_policy->work_in_progress = false;" in after_target
assert "mutex_lock(&sg_policy->work_lock);" in w
assert "raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);" in w
stop = s.split("static int esgov_stop(", 1)[1].split("static int esgov_limits(", 1)[0]
assert stop.index("sg_policy->stopping = true;") < stop.index("irq_work_sync(")
single = s.split("static void esgov_update_single(", 1)[1].split("static unsigned int esgov_next_freq_shared(", 1)[0]
assert single.index("raw_spin_lock(") < single.index("esgov_should_update_freq(")
assert "goto unlock;" in single
init = s.split("static int esgov_init(", 1)[1].split("static int esgov_exit(", 1)[0]
assert "mutex_unlock" not in init.split("free_sg_policy:", 1)[1]
print("PASS: bounded replay, synchronized stop and policy snapshot, correct init cleanup")
