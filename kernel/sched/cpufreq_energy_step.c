/*
 * ALICE EnergyStep-compat cpufreq governor for Exynos8895.
 * Uses discrete policy frequency steps, scheduler utilization and rate hysteresis.
 *
 * Copyright (C) 2016, Intel Corporation
 * Author: Rafael J. Wysocki <rafael.j.wysocki@intel.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation.
 */

#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/cpufreq.h>
#include <linux/kthread.h>
#include <linux/slab.h>
#include <trace/events/power.h>

#include "sched.h"
#include "tune.h"

unsigned long boosted_cpu_util(int cpu);

/* Stub out fast switch routines present on mainline to reduce the backport
 * overhead. */
#define cpufreq_driver_fast_switch(x, y) 0
#define cpufreq_enable_fast_switch(x)
#define cpufreq_disable_fast_switch(x)
#define ESGOV_DEFAULT_UP_RATE_LIMIT_US		(3000)
#define ESGOV_DEFAULT_DOWN_RATE_LIMIT_US	(12000)
#define ESGOV_KTHREAD_PRIORITY	50

struct esgov_tunables {
	struct gov_attr_set attr_set;
	unsigned int up_rate_limit_us;
	unsigned int down_rate_limit_us;
};

struct esgov_policy {
	struct cpufreq_policy *policy;

	struct esgov_tunables *tunables;
	struct list_head tunables_hook;

	raw_spinlock_t update_lock;  /* For shared policies */
	u64 last_freq_update_time;
	s64 min_rate_limit_ns;
	s64 up_rate_delay_ns;
	s64 down_rate_delay_ns;
	unsigned int next_freq;
	unsigned int cached_raw_freq;

	/* The next fields are only needed if fast switch cannot be used. */
	struct irq_work irq_work;
	struct kthread_work work;
	struct mutex work_lock;
	struct kthread_worker worker;
	struct task_struct *thread;
	bool work_in_progress;
	bool stopping;

	bool need_freq_update;
};

struct esgov_cpu {
	struct update_util_data update_util;
	struct esgov_policy *sg_policy;

	bool iowait_boost_pending;
	unsigned int iowait_boost;
	unsigned int iowait_boost_max;
	u64 last_update;

	/* The fields below are only needed when sharing a policy. */
	unsigned long util;
	unsigned long max;
	unsigned int flags;

	/* The field below is for single-CPU policies only. */
#ifdef CONFIG_NO_HZ_COMMON
	unsigned long saved_idle_calls;
#endif
};

static DEFINE_PER_CPU(struct esgov_cpu, esgov_cpu);
static DEFINE_PER_CPU(struct esgov_tunables *, cached_tunables);
static unsigned int stale_ns;

/************************ Governor internals ***********************/

static bool esgov_should_update_freq(struct esgov_policy *sg_policy, u64 time)
{
	s64 delta_ns;

	if (unlikely(sg_policy->need_freq_update))
		return true;

	delta_ns = time - sg_policy->last_freq_update_time;

	/* No need to recalculate next freq for min_rate_limit_us at least */
	return delta_ns >= sg_policy->min_rate_limit_ns;
}

static bool esgov_up_down_rate_limit(struct esgov_policy *sg_policy, u64 time,
				     unsigned int next_freq)
{
	s64 delta_ns;

	delta_ns = time - sg_policy->last_freq_update_time;

	if (next_freq > sg_policy->next_freq &&
	    delta_ns < sg_policy->up_rate_delay_ns)
			return true;

	if (next_freq < sg_policy->next_freq &&
	    delta_ns < sg_policy->down_rate_delay_ns)
			return true;

	return false;
}

static void esgov_update_commit(struct esgov_policy *sg_policy, u64 time,
				unsigned int next_freq)
{
	struct cpufreq_policy *policy = sg_policy->policy;

	if (unlikely(sg_policy->stopping))
		return;

	if (esgov_up_down_rate_limit(sg_policy, time, next_freq)) {
		/* Reset cached freq as next_freq isn't changed */
		sg_policy->cached_raw_freq = 0;
		return;
	}

	if (sg_policy->next_freq == next_freq)
		return;

	sg_policy->next_freq = next_freq;
	sg_policy->last_freq_update_time = time;

	if (policy->fast_switch_enabled) {
		next_freq = cpufreq_driver_fast_switch(policy, next_freq);
		if (next_freq == CPUFREQ_ENTRY_INVALID)
			return;

		policy->cur = next_freq;
		trace_cpu_frequency(next_freq, smp_processor_id());
	} else if (!sg_policy->work_in_progress) {
		sg_policy->work_in_progress = true;
		irq_work_queue(&sg_policy->irq_work);
	}
}

/**
 * get_next_freq - Compute a new frequency for a given cpufreq policy.
 * @sg_policy: energy_step policy object to compute the new frequency for.
 * @util: Current CPU utilization.
 * @max: CPU capacity.
 *
 * If the utilization is frequency-invariant, choose the new frequency to be
 * proportional to it, that is
 *
 * next_freq = C * max_freq * util / max
 *
 * Otherwise, approximate the would-be frequency-invariant utilization by
 * util_raw * (curr_freq / max_freq) which leads to
 *
 * next_freq = C * curr_freq * util_raw / max
 *
 * Take C = 1.125 for the frequency tipping point at (util / max) = 8/9.
 *
 * The lowest driver-supported frequency which is equal or greater than the raw
 * next_freq (as calculated above) is returned, subject to policy min/max and
 * cpufreq driver limitations.
 */
/*
 * ALICE EnergyStep-compat for Linux 4.4 / Exynos8895 (V12R69 R6).
 *
 * Samsung's genuine energy_step (2019+) relies on EMS energy-table hooks,
 * emstune, uclamp and vendor tracepoints missing from the Exynos8895 tree.
 * We preserve this tree's proven WALT/PELT, IOWAIT and cpufreq workqueue,
 * with 112.5% headroom and the driver's discrete frequency steps.
 * This is NOT Samsung EMS energy_step.
 *
 * Resolve only once: eight synthetic linear buckets followed by driver
 * rounding could skip a sufficient hardware step and raise voltage needlessly.
 * Driver resolution respects policy min/max and thermal/QoS constraints.
 * The up/down rate limits retain hysteresis.
 */
static unsigned int esgov_step_target(struct cpufreq_policy *policy,
				     unsigned int requested)
{
	unsigned int index;

	requested = clamp(requested, policy->min, policy->max);
	/* Exynos uses legacy .target: resolve_freq() alone returns the raw
	 * request for that driver. Quantize against its real table before
	 * committing, so requests in one hardware step don't wake the worker.
	 */
	if (policy->freq_table &&
	    !cpufreq_frequency_table_target(policy, policy->freq_table,
			requested, CPUFREQ_RELATION_L, &index))
		return policy->freq_table[index].frequency;

	return cpufreq_driver_resolve_freq(policy, requested);
}

static unsigned int get_next_freq(struct esgov_policy *sg_policy,
				  unsigned long util, unsigned long max)
{
	struct cpufreq_policy *policy = sg_policy->policy;
	unsigned int base = arch_scale_freq_invariant() ?
				policy->cpuinfo.max_freq : policy->cur;
	unsigned int raw;

	if (unlikely(!max))
		return policy->min;

	/* Conservative frequency headroom (112.5%). */
	raw = div64_u64((u64)(base + (base >> 3)) * util, max);

	if (raw == sg_policy->cached_raw_freq && !sg_policy->need_freq_update)
		return sg_policy->next_freq;

	sg_policy->need_freq_update = false;
	sg_policy->cached_raw_freq = raw;
	return esgov_step_target(policy, raw);
}

static inline bool use_pelt(void)
{
#ifdef CONFIG_SCHED_WALT
	return (!sysctl_sched_use_walt_cpu_util || walt_disabled);
#else
	return true;
#endif
}

static void esgov_get_util(unsigned long *util, unsigned long *max, u64 time)
{
	int cpu = smp_processor_id();
	struct rq *rq = cpu_rq(cpu);
	unsigned long max_cap, rt;
	s64 delta;

	max_cap = arch_scale_cpu_capacity(NULL, cpu);

	sched_avg_update(rq);
	delta = time - rq->age_stamp;
	if (unlikely(delta < 0))
		delta = 0;
	rt = div64_u64(rq->rt_avg, sched_avg_period() + delta);
	rt = (rt * max_cap) >> SCHED_CAPACITY_SHIFT;

	*util = boosted_cpu_util(cpu);
	if (use_pelt())
		*util = *util + rt;

	*util = min(*util, max_cap);
	*max = max_cap;
}

static void esgov_set_iowait_boost(struct esgov_cpu *sg_cpu, u64 time,
				   unsigned int flags)
{
	if (flags & SCHED_CPUFREQ_IOWAIT) {
		if (sg_cpu->iowait_boost_pending)
			return;

		sg_cpu->iowait_boost_pending = true;

		if (sg_cpu->iowait_boost) {
			sg_cpu->iowait_boost <<= 1;
			if (sg_cpu->iowait_boost > sg_cpu->iowait_boost_max)
				sg_cpu->iowait_boost = sg_cpu->iowait_boost_max;
		} else {
			sg_cpu->iowait_boost = sg_cpu->sg_policy->policy->min;
		}
	} else if (sg_cpu->iowait_boost) {
		s64 delta_ns = time - sg_cpu->last_update;

		/* Clear iowait_boost if the CPU apprears to have been idle. */
		if (delta_ns > TICK_NSEC) {
			sg_cpu->iowait_boost = 0;
			sg_cpu->iowait_boost_pending = false;
		}
	}
}

static void esgov_iowait_boost(struct esgov_cpu *sg_cpu, unsigned long *util,
			       unsigned long *max)
{
	unsigned int boost_util, boost_max;

	if (!sg_cpu->iowait_boost)
		return;

	if (sg_cpu->iowait_boost_pending) {
		sg_cpu->iowait_boost_pending = false;
	} else {
		sg_cpu->iowait_boost >>= 1;
		if (sg_cpu->iowait_boost < sg_cpu->sg_policy->policy->min) {
			sg_cpu->iowait_boost = 0;
			return;
		}
	}

	boost_util = sg_cpu->iowait_boost;
	boost_max = sg_cpu->iowait_boost_max;

	if (*util * boost_max < *max * boost_util) {
		*util = boost_util;
		*max = boost_max;
	}
}

#ifdef CONFIG_NO_HZ_COMMON
static bool esgov_cpu_is_busy(struct esgov_cpu *sg_cpu)
{
	unsigned long idle_calls = tick_nohz_get_idle_calls();
	bool ret = idle_calls == sg_cpu->saved_idle_calls;

	sg_cpu->saved_idle_calls = idle_calls;
	return ret;
}
#else
static inline bool esgov_cpu_is_busy(struct esgov_cpu *sg_cpu) { return false; }
#endif /* CONFIG_NO_HZ_COMMON */

static void esgov_update_single(struct update_util_data *hook, u64 time,
				unsigned int flags)
{
	struct esgov_cpu *sg_cpu = container_of(hook, struct esgov_cpu, update_util);
	struct esgov_policy *sg_policy = sg_cpu->sg_policy;
	struct cpufreq_policy *policy = sg_policy->policy;
	unsigned long util, max;
	unsigned int next_f;
	bool busy;

	esgov_set_iowait_boost(sg_cpu, time, flags);
	sg_cpu->last_update = time;

	/* Protect the complete policy snapshot, not just the final commit. */
	raw_spin_lock(&sg_policy->update_lock);
	if (!esgov_should_update_freq(sg_policy, time))
		goto unlock;

	busy = esgov_cpu_is_busy(sg_cpu);

	if (flags & SCHED_CPUFREQ_DL) {
		next_f = esgov_step_target(policy, policy->max);
	} else {
		esgov_get_util(&util, &max, time);
		esgov_iowait_boost(sg_cpu, &util, &max);
		next_f = get_next_freq(sg_policy, util, max);
		/*
		 * Do not reduce the frequency if the CPU has not been idle
		 * recently, as the reduction is likely to be premature then.
		 */
		if (busy && next_f < sg_policy->next_freq) {
			next_f = sg_policy->next_freq;

			/* Reset cached freq as next_freq has changed */
			sg_policy->cached_raw_freq = 0;
		}
	}
	esgov_update_commit(sg_policy, time, next_f);
unlock:
	raw_spin_unlock(&sg_policy->update_lock);
}

static unsigned int esgov_next_freq_shared(struct esgov_cpu *sg_cpu, u64 time)
{
	struct esgov_policy *sg_policy = sg_cpu->sg_policy;
	struct cpufreq_policy *policy = sg_policy->policy;
	unsigned long util = 0, max = 1;
	unsigned int j;

	for_each_cpu(j, policy->cpus) {
		struct esgov_cpu *j_sg_cpu = &per_cpu(esgov_cpu, j);
		unsigned long j_util, j_max;
		s64 delta_ns;

		/* Hotplug/start leaves capacity zero until the first real sample. */
		if (!j_sg_cpu->max)
			continue;

		/*
		 * If the CPU utilization was last updated before the previous
		 * frequency update and the time elapsed between the last update
		 * of the CPU utilization and the last frequency update is long
		 * enough, don't take the CPU into account as it probably is
		 * idle now (and clear iowait_boost for it).
		 */
		delta_ns = time - j_sg_cpu->last_update;
		if (delta_ns > stale_ns) {
			j_sg_cpu->iowait_boost = 0;
			j_sg_cpu->iowait_boost_pending = false;
			continue;
		}
		if (j_sg_cpu->flags & SCHED_CPUFREQ_DL)
			return esgov_step_target(policy, policy->max);

		j_util = j_sg_cpu->util;
		j_max = j_sg_cpu->max;
		if (j_util * max >= j_max * util) {
			util = j_util;
			max = j_max;
		}

		esgov_iowait_boost(j_sg_cpu, &util, &max);
	}

	return get_next_freq(sg_policy, util, max);
}

static void esgov_update_shared(struct update_util_data *hook, u64 time,
				unsigned int flags)
{
	struct esgov_cpu *sg_cpu = container_of(hook, struct esgov_cpu, update_util);
	struct esgov_policy *sg_policy = sg_cpu->sg_policy;
	unsigned long util, max;
	unsigned int next_f;

	esgov_get_util(&util, &max, time);

	raw_spin_lock(&sg_policy->update_lock);

	sg_cpu->util = util;
	sg_cpu->max = max;
	sg_cpu->flags = flags;

	esgov_set_iowait_boost(sg_cpu, time, flags);
	sg_cpu->last_update = time;

	if (esgov_should_update_freq(sg_policy, time)) {
		if (flags & SCHED_CPUFREQ_DL)
			next_f = esgov_step_target(sg_policy->policy, sg_policy->policy->max);
		else
			next_f = esgov_next_freq_shared(sg_cpu, time);

		esgov_update_commit(sg_policy, time, next_f);
	}

	raw_spin_unlock(&sg_policy->update_lock);
}

static void esgov_work(struct kthread_work *work)
{
	struct esgov_policy *sg_policy = container_of(work, struct esgov_policy, work);
	unsigned int freq;
	unsigned long flags;
	int attempt;
	int ret;
	bool requeue = false;

	/*
	 * Keep work_in_progress set until the current target completes.
	 * Drain at most two requests so an endless UI utilization stream
	 * cannot monopolize the cpufreq kthread.  If more updates arrive,
	 * schedule a fresh work item instead of losing the latest target.
	 */
	mutex_lock(&sg_policy->work_lock);
	for (attempt = 0; attempt < 2; attempt++) {
		raw_spin_lock_irqsave(&sg_policy->update_lock, flags);
		if (sg_policy->stopping) {
			sg_policy->work_in_progress = false;
			raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);
			break;
		}
		freq = sg_policy->next_freq;
		raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);

		ret = __cpufreq_driver_target(sg_policy->policy, freq,
					CPUFREQ_RELATION_L);

		raw_spin_lock_irqsave(&sg_policy->update_lock, flags);
		if (ret) {
			/* A rejected target was not applied. Invalidate the cache
			 * so a later scheduler update can retry even at identical
			 * utilization. Do not spin on a failing driver here.
			 */
			sg_policy->next_freq = 0;
			sg_policy->cached_raw_freq = 0;
			sg_policy->need_freq_update = true;
			sg_policy->work_in_progress = false;
			raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);
			break;
		}
		if (sg_policy->stopping || sg_policy->next_freq == freq) {
			sg_policy->work_in_progress = false;
			raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);
			break;
		}
		if (attempt == 1) {
			/*
			 * Requeue directly on this worker. Its executing work is
			 * off the pending list, and queue_kthread_work() serializes
			 * cancellation. An IRQ queued here could otherwise outlive
			 * esgov_stop()'s irq_work_sync() and access a freed policy.
			 */
			requeue = true;
		}
		raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);
	}
	/* Queueing may wake a task and take rq->lock, whose cpufreq hook
	 * needs update_lock. Never queue while holding the policy lock.
	 * kthread_cancel_work_sync() also prevents this self-requeue while
	 * stop waits for the currently executing work to finish.
	 */
	if (requeue)
		queue_kthread_work(&sg_policy->worker, &sg_policy->work);
	mutex_unlock(&sg_policy->work_lock);
}

static void esgov_irq_work(struct irq_work *irq_work)
{
	struct esgov_policy *sg_policy;
	unsigned long flags;
	bool queue;

	sg_policy = container_of(irq_work, struct esgov_policy, irq_work);

	raw_spin_lock_irqsave(&sg_policy->update_lock, flags);
	queue = !sg_policy->stopping;
	raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);
	/* A worker wakeup can re-enter cpufreq under rq->lock. Stop drains
	 * this IRQ callback before cancelling work, so its unlocked enqueue
	 * cannot outlive the cancellation even if stopping changes here.
	 */
	if (queue)
		queue_kthread_work(&sg_policy->worker, &sg_policy->work);
}

/************************** sysfs interface ************************/

static struct esgov_tunables *global_tunables;
static DEFINE_MUTEX(global_tunables_lock);

static inline struct esgov_tunables *to_esgov_tunables(struct gov_attr_set *attr_set)
{
	return container_of(attr_set, struct esgov_tunables, attr_set);
}

static void update_min_rate_limit_us(struct esgov_policy *sg_policy)
{
	/* Caller holds update_lock, or is starting before hooks are installed. */
	sg_policy->min_rate_limit_ns = min(sg_policy->up_rate_delay_ns,
					   sg_policy->down_rate_delay_ns);
}

static ssize_t up_rate_limit_us_show(struct gov_attr_set *attr_set, char *buf)
{
	struct esgov_tunables *tunables = to_esgov_tunables(attr_set);

	return sprintf(buf, "%u\n", tunables->up_rate_limit_us);
}

static ssize_t down_rate_limit_us_show(struct gov_attr_set *attr_set, char *buf)
{
	struct esgov_tunables *tunables = to_esgov_tunables(attr_set);

	return sprintf(buf, "%u\n", tunables->down_rate_limit_us);
}

static ssize_t up_rate_limit_us_store(struct gov_attr_set *attr_set,
				      const char *buf, size_t count)
{
	struct esgov_tunables *tunables = to_esgov_tunables(attr_set);
	struct esgov_policy *sg_policy;
	unsigned int rate_limit_us;
	unsigned long flags;

	if (kstrtouint(buf, 10, &rate_limit_us))
		return -EINVAL;

	tunables->up_rate_limit_us = rate_limit_us;

	list_for_each_entry(sg_policy, &attr_set->policy_list, tunables_hook) {
		raw_spin_lock_irqsave(&sg_policy->update_lock, flags);
		sg_policy->up_rate_delay_ns = (u64)rate_limit_us * NSEC_PER_USEC;
		update_min_rate_limit_us(sg_policy);
		raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);
	}

	return count;
}

static ssize_t down_rate_limit_us_store(struct gov_attr_set *attr_set,
					const char *buf, size_t count)
{
	struct esgov_tunables *tunables = to_esgov_tunables(attr_set);
	struct esgov_policy *sg_policy;
	unsigned int rate_limit_us;
	unsigned long flags;

	if (kstrtouint(buf, 10, &rate_limit_us))
		return -EINVAL;

	tunables->down_rate_limit_us = rate_limit_us;

	list_for_each_entry(sg_policy, &attr_set->policy_list, tunables_hook) {
		raw_spin_lock_irqsave(&sg_policy->update_lock, flags);
		sg_policy->down_rate_delay_ns = (u64)rate_limit_us * NSEC_PER_USEC;
		update_min_rate_limit_us(sg_policy);
		raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);
	}

	return count;
}

static struct governor_attr up_rate_limit_us = __ATTR_RW(up_rate_limit_us);
static struct governor_attr down_rate_limit_us = __ATTR_RW(down_rate_limit_us);

static struct attribute *esgov_attributes[] = {
	&up_rate_limit_us.attr,
	&down_rate_limit_us.attr,
	NULL
};

static struct kobj_type esgov_tunables_ktype = {
	.default_attrs = esgov_attributes,
	.sysfs_ops = &governor_sysfs_ops,
};

/********************** cpufreq governor interface *********************/
#ifndef CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYSTEP
static
#endif
struct cpufreq_governor cpufreq_gov_energy_step;

static struct esgov_policy *esgov_policy_alloc(struct cpufreq_policy *policy)
{
	struct esgov_policy *sg_policy;

	sg_policy = kzalloc(sizeof(*sg_policy), GFP_KERNEL);
	if (!sg_policy)
		return NULL;

	sg_policy->policy = policy;
	raw_spin_lock_init(&sg_policy->update_lock);
	return sg_policy;
}

static void esgov_policy_free(struct esgov_policy *sg_policy)
{
	kfree(sg_policy);
}

static int esgov_kthread_create(struct esgov_policy *sg_policy)
{
	struct task_struct *thread;
	struct sched_param param = { .sched_priority = MAX_USER_RT_PRIO / 2 };
	struct cpufreq_policy *policy = sg_policy->policy;
	int ret;

	/* kthread only required for slow path */
	if (policy->fast_switch_enabled)
		return 0;

	init_kthread_work(&sg_policy->work, esgov_work);
	init_kthread_worker(&sg_policy->worker);
	thread = kthread_create(kthread_worker_fn, &sg_policy->worker,
				"esgov:%d",
				cpumask_first(policy->related_cpus));
	if (IS_ERR(thread)) {
		pr_err("failed to create esgov thread: %ld\n", PTR_ERR(thread));
		return PTR_ERR(thread);
	}

	ret = sched_setscheduler_nocheck(thread, SCHED_FIFO, &param);
	if (ret) {
		kthread_stop(thread);
		pr_warn("%s: failed to set SCHED_FIFO\n", __func__);
		return ret;
	}

	sg_policy->thread = thread;
	kthread_bind_mask(thread, policy->related_cpus);
	init_irq_work(&sg_policy->irq_work, esgov_irq_work);
	mutex_init(&sg_policy->work_lock);

	wake_up_process(thread);

	return 0;
}

static void esgov_kthread_stop(struct esgov_policy *sg_policy)
{
	/* kthread only required for slow path */
	if (sg_policy->policy->fast_switch_enabled)
		return;

	flush_kthread_worker(&sg_policy->worker);
	kthread_stop(sg_policy->thread);
	mutex_destroy(&sg_policy->work_lock);
}

static struct esgov_tunables *esgov_tunables_alloc(struct esgov_policy *sg_policy)
{
	struct esgov_tunables *tunables;

	tunables = kzalloc(sizeof(*tunables), GFP_KERNEL);
	if (tunables) {
		gov_attr_set_init(&tunables->attr_set, &sg_policy->tunables_hook);
		if (!have_governor_per_policy())
			global_tunables = tunables;
	}
	return tunables;
}

static void esgov_tunables_save(struct cpufreq_policy *policy,
		struct esgov_tunables *tunables)
{
	int cpu;
	struct esgov_tunables *cached = per_cpu(cached_tunables, policy->cpu);

	if (!have_governor_per_policy())
		return;

	if (!cached) {
		cached = kzalloc(sizeof(*tunables), GFP_KERNEL);
		if (!cached) {
			pr_warn("Couldn't allocate tunables for caching\n");
			return;
		}
		for_each_cpu(cpu, policy->related_cpus)
			per_cpu(cached_tunables, cpu) = cached;
	}

	cached->up_rate_limit_us = tunables->up_rate_limit_us;
	cached->down_rate_limit_us = tunables->down_rate_limit_us;
}

static void esgov_tunables_free(struct esgov_tunables *tunables)
{
	if (!have_governor_per_policy())
		global_tunables = NULL;

	kfree(tunables);
}

static void esgov_tunables_restore(struct cpufreq_policy *policy)
{
	struct esgov_policy *sg_policy = policy->governor_data;
	struct esgov_tunables *tunables = sg_policy->tunables;
	struct esgov_tunables *cached = per_cpu(cached_tunables, policy->cpu);

	if (!cached)
		return;

	tunables->up_rate_limit_us = cached->up_rate_limit_us;
	tunables->down_rate_limit_us = cached->down_rate_limit_us;
	sg_policy->up_rate_delay_ns =
		(u64)tunables->up_rate_limit_us * NSEC_PER_USEC;
	sg_policy->down_rate_delay_ns =
		(u64)tunables->down_rate_limit_us * NSEC_PER_USEC;
	sg_policy->min_rate_limit_ns = min(sg_policy->up_rate_delay_ns,
					   sg_policy->down_rate_delay_ns);
}

static int esgov_init(struct cpufreq_policy *policy)
{
	struct esgov_policy *sg_policy;
	struct esgov_tunables *tunables;
	int ret = 0;

	/* State should be equivalent to EXIT */
	if (policy->governor_data)
		return -EBUSY;

	cpufreq_enable_fast_switch(policy);

	sg_policy = esgov_policy_alloc(policy);
	if (!sg_policy) {
		ret = -ENOMEM;
		goto disable_fast_switch;
	}

	ret = esgov_kthread_create(sg_policy);
	if (ret)
		goto free_sg_policy;

	mutex_lock(&global_tunables_lock);

	if (global_tunables) {
		if (WARN_ON(have_governor_per_policy())) {
			ret = -EINVAL;
			goto stop_kthread;
		}
		policy->governor_data = sg_policy;
		sg_policy->tunables = global_tunables;

		gov_attr_set_get(&global_tunables->attr_set, &sg_policy->tunables_hook);
		goto out;
	}

	tunables = esgov_tunables_alloc(sg_policy);
	if (!tunables) {
		ret = -ENOMEM;
		goto stop_kthread;
	}

	if (policy->up_transition_delay_us && policy->down_transition_delay_us) {
		tunables->up_rate_limit_us = policy->up_transition_delay_us;
		tunables->down_rate_limit_us = policy->down_transition_delay_us;
	} else {
		/*
		 * Exynos8895 does not publish separate transition delays.  Scaling
		 * the hardware latency by 1000 delayed both directions by about
		 * 100 ms, which is visible as launch and scrolling stutter.  Use a
		 * short 3 ms response window, then release a stale high OPP after
		 * 12 ms. This keeps UI bursts responsive without pinning the Exynos M2
		 * cluster at an overclocked OPP between frames.
		 */
		tunables->up_rate_limit_us = ESGOV_DEFAULT_UP_RATE_LIMIT_US;
		tunables->down_rate_limit_us = ESGOV_DEFAULT_DOWN_RATE_LIMIT_US;
	}

	policy->governor_data = sg_policy;
	sg_policy->tunables = tunables;
	stale_ns = walt_ravg_window + (walt_ravg_window >> 3);

	esgov_tunables_restore(policy);

	ret = kobject_init_and_add(&tunables->attr_set.kobj, &esgov_tunables_ktype,
				   get_governor_parent_kobj(policy), "%s",
				   cpufreq_gov_energy_step.name);
	if (ret)
		goto fail;

out:
	mutex_unlock(&global_tunables_lock);
	return 0;

fail:
	policy->governor_data = NULL;
	esgov_tunables_free(tunables);

stop_kthread:
	mutex_unlock(&global_tunables_lock);
	esgov_kthread_stop(sg_policy);

free_sg_policy:
	esgov_policy_free(sg_policy);

disable_fast_switch:
	cpufreq_disable_fast_switch(policy);

	pr_err("initialization failed (error %d)\n", ret);
	return ret;
}

static int esgov_exit(struct cpufreq_policy *policy)
{
	struct esgov_policy *sg_policy = policy->governor_data;
	struct esgov_tunables *tunables = sg_policy->tunables;
	unsigned int count;

	mutex_lock(&global_tunables_lock);

	count = gov_attr_set_put(&tunables->attr_set, &sg_policy->tunables_hook);
	policy->governor_data = NULL;
	if (!count) {
		esgov_tunables_save(policy, tunables);
		esgov_tunables_free(tunables);
	}

	mutex_unlock(&global_tunables_lock);

	esgov_kthread_stop(sg_policy);
	esgov_policy_free(sg_policy);

	cpufreq_disable_fast_switch(policy);
	return 0;
}

static int esgov_start(struct cpufreq_policy *policy)
{
	struct esgov_policy *sg_policy = policy->governor_data;
	unsigned int cpu;

	sg_policy->up_rate_delay_ns =
		(u64)sg_policy->tunables->up_rate_limit_us * NSEC_PER_USEC;
	sg_policy->down_rate_delay_ns =
		(u64)sg_policy->tunables->down_rate_limit_us * NSEC_PER_USEC;
	update_min_rate_limit_us(sg_policy);
	sg_policy->last_freq_update_time = 0;
	sg_policy->next_freq = 0;
	sg_policy->work_in_progress = false;
	sg_policy->stopping = false;
	sg_policy->need_freq_update = false;
	sg_policy->cached_raw_freq = 0;

	for_each_cpu(cpu, policy->cpus) {
		struct esgov_cpu *sg_cpu = &per_cpu(esgov_cpu, cpu);

		memset(sg_cpu, 0, sizeof(*sg_cpu));
		sg_cpu->sg_policy = sg_policy;
		/* No synthetic deadline load on CPUs with no scheduler sample. */
		sg_cpu->flags = 0;
		sg_cpu->iowait_boost_max = policy->cpuinfo.max_freq;
	}

	for_each_cpu(cpu, policy->cpus) {
		struct esgov_cpu *sg_cpu = &per_cpu(esgov_cpu, cpu);

		cpufreq_add_update_util_hook(cpu, &sg_cpu->update_util,
					     policy_is_shared(policy) ?
							esgov_update_shared :
							esgov_update_single);
	}
	return 0;
}

static int esgov_stop(struct cpufreq_policy *policy)
{
	struct esgov_policy *sg_policy = policy->governor_data;
	unsigned int cpu;
	unsigned long flags;

	for_each_cpu(cpu, policy->cpus)
		cpufreq_remove_update_util_hook(cpu);

	synchronize_sched();

	/* Block worker replay before draining IRQ work and cancelling work. */
	raw_spin_lock_irqsave(&sg_policy->update_lock, flags);
	sg_policy->stopping = true;
	raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);

	if (!policy->fast_switch_enabled) {
		irq_work_sync(&sg_policy->irq_work);
		kthread_cancel_work_sync(&sg_policy->work);
	}
	return 0;
}

static int esgov_limits(struct cpufreq_policy *policy)
{
	struct esgov_policy *sg_policy = policy->governor_data;
	unsigned long flags;

	if (!policy->fast_switch_enabled) {
		mutex_lock(&sg_policy->work_lock);
		cpufreq_policy_apply_limits(policy);
		mutex_unlock(&sg_policy->work_lock);
	}

	raw_spin_lock_irqsave(&sg_policy->update_lock, flags);
	sg_policy->need_freq_update = true;
	sg_policy->cached_raw_freq = 0;
	raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);

	return 0;
}

static int cpufreq_energy_step_cb(struct cpufreq_policy *policy,
				unsigned int event)
{
	switch(event) {
	case CPUFREQ_GOV_POLICY_INIT:
		return esgov_init(policy);
	case CPUFREQ_GOV_POLICY_EXIT:
		return esgov_exit(policy);
	case CPUFREQ_GOV_START:
		return esgov_start(policy);
	case CPUFREQ_GOV_STOP:
		return esgov_stop(policy);
	case CPUFREQ_GOV_LIMITS:
		return esgov_limits(policy);
	default:
		BUG();
	}
}

#ifndef CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYSTEP
static
#endif
struct cpufreq_governor cpufreq_gov_energy_step = {
	.name = "energy_step",
	.governor = cpufreq_energy_step_cb,
	.owner = THIS_MODULE,
};

static int __init esgov_register(void)
{
	return cpufreq_register_governor(&cpufreq_gov_energy_step);
}
fs_initcall(esgov_register);
