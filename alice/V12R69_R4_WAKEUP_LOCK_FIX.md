# V12R69 R4: EnergyStep worker wakeup lock ordering

R3 enqueued the cpufreq worker while holding the policy update_lock.
queue_kthread_work() can wake a sleeping worker and enter the scheduler.
Scheduler code takes rq->lock and may call the governor, which needs the same
policy lock. This creates a recursive lock or an rq/policy lock inversion.

R4 snapshots the IRQ enqueue decision under update_lock, releases the lock,
and then enqueues. Worker replay also enqueues after releasing update_lock.
The bounded two-pass worker and target/error handling are preserved.

Stop first removes scheduler hooks, sets stopping, drains the IRQ callback,
and cancels the worker synchronously. An IRQ that captured its enqueue decision
before stopping must finish its enqueue before cancellation proceeds.
The kthread cancellation counter blocks self-requeue while cancellation waits.

The C regression now models the scheduler reacquiring the policy lock at worker
wakeup. R3 fails; R4 passes. It also covers stop while an IRQ enqueue is in
flight, stop during a driver transition, bounded replay, and driver rejection.

MGLRU, PSI and low-swap repairs from R3 remain. The default governor remains
EnergyStep and the kernel remains enforcing with KernelSU 32590. The separate
LMKD helper is not applied by the kernel. Host tests and CI do not establish
physical S8+ boot or runtime stability.
