/*
 * ALice energy-model-driven CPUFreq governor for Exynos8895.
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
#include <linux/sched_energy.h>
#include <linux/math64.h>
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
#define EAGOV_DEFAULT_UP_RATE_LIMIT_US		(3000)
#define EAGOV_DEFAULT_DOWN_RATE_LIMIT_US	(12000)
#define EAGOV_KTHREAD_PRIORITY	50

struct eagov_tunables {
	struct gov_attr_set attr_set;
	unsigned int up_rate_limit_us;
	unsigned int down_rate_limit_us;
};

struct eagov_policy {
	struct cpufreq_policy *policy;

	struct eagov_tunables *tunables;
	struct list_head tunables_hook;

	raw_spinlock_t update_lock;  /* For shared policies */
	u64 last_freq_update_time;
	s64 min_rate_limit_ns;
	s64 up_rate_delay_ns;
	s64 down_rate_delay_ns;
	unsigned int next_freq;

	/* The next fields are only needed if fast switch cannot be used. */
	struct irq_work irq_work;
	struct kthread_work work;
	struct mutex work_lock;
	struct kthread_worker worker;
	struct task_struct *thread;
	bool work_in_progress;

	bool need_freq_update;
};

struct eagov_cpu {
	struct update_util_data update_util;
	struct eagov_policy *sg_policy;

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

static DEFINE_PER_CPU(struct eagov_cpu, eagov_cpu);
static DEFINE_PER_CPU(struct eagov_tunables *, cached_tunables);
static unsigned int stale_ns;

/************************ Governor internals ***********************/

static bool eagov_should_update_freq(struct eagov_policy *sg_policy, u64 time)
{
	s64 delta_ns;

	if (unlikely(sg_policy->need_freq_update))
		return true;

	delta_ns = time - sg_policy->last_freq_update_time;

	/* No need to recalculate next freq for min_rate_limit_us at least */
	return delta_ns >= sg_policy->min_rate_limit_ns;
}

static bool eagov_up_down_rate_limit(struct eagov_policy *sg_policy, u64 time,
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

static void eagov_update_commit(struct eagov_policy *sg_policy, u64 time,
				unsigned int next_freq)
{
	struct cpufreq_policy *policy = sg_policy->policy;

	if (eagov_up_down_rate_limit(sg_policy, time, next_freq))
		return;

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

/*
 * ALice EAM v3: Samsung A53 EGO OPP search on Exynos8895 energy costs.
 *
 * The DTS sched-energy-costs tables expose a capacity and a busy power for
 * each core OPP, plus separate cluster power and idle-state costs.  We
 * evaluate the energy needed to execute the current policy's workload over
 * one scheduler window (core work SUM, cluster active time PEAK), constrained
 * by the highest per-CPU utilization and a modest capacity headroom.
 *
 * This is deliberately NOT schedutil's (util * max_freq / max_capacity)
 * frequency computation.  Utilization only describes the work requirement;
 * the energy model, rather than a proportional clock target, picks the OPP.
 *
 * Retain the Linux 4.4 scheduler callback, IOWAIT, RT/DL and slow cpufreq
 * transition infrastructure for the Exynos8895 hardware.  This is not the
 * Samsung 5.10 EMS/EGO task-placement subsystem shipped on Exynos1280.
 */
#define EAGOV_LOAD_SCALE            (1UL << SCHED_CAPACITY_SHIFT)
#define EAGOV_CAPACITY_MARGIN_NUM   9U
#define EAGOV_CAPACITY_MARGIN_DEN   8U

static unsigned long eagov_util_to_load(unsigned long util,
                                        unsigned long capacity)
{
    if (unlikely(!capacity))
        return 0;

    return (unsigned long)div64_u64(
                (u64)min(util, capacity) * EAGOV_LOAD_SCALE, capacity);
}

/*
 * EGO (Exynos1280)-inspired energy evaluation, adapted to Exynos8895:
 *
 *  1. Work out the minimum capacity required by the most loaded CPU.
 *  2. Walk the *real cpufreq OPP table*, not a proportional target.
 *  3. Reject any OPP which cannot supply that capacity.
 *  4. Estimate busy and idle energy across the whole cluster using
 *     Exynos8895 DTS sched-energy-costs (core + shared cluster).
 *  5. Select the OPP with lowest predicted energy.
 *
 * The Samsung EGO source uses et_freq_to_cap()/et_compute_cpu_energy(),
 * MLT idle ratios, emstune and fclamp.  Those interfaces do not exist in
 * this Linux 4.4 kernel.  These computations are a native 4.4 adaptation
 * of that algorithm, NOT a copy of the whole Samsung EMS framework.
 *
 * The original Samsung ESG energy_step.c source is archived as a separate
 * reference.  We use the same capacity/power distinction, but keep only
 * the energy_aware governor registered and enabled.
 */
static unsigned int eagov_energy_model_freq(struct eagov_policy *sg_policy,
                                            unsigned long peak_load,
                                            unsigned long total_load)
{
    struct cpufreq_policy *policy = sg_policy->policy;
    struct cpufreq_frequency_table *opp;
    const struct sched_group_energy *core, *cluster;
    unsigned long max_cap = 0, required, core_idle, cluster_idle;
    unsigned int best_freq = policy->max;
    u64 best_energy = U64_MAX;
    bool found = false;
    int i;

    if (unlikely(!peak_load))
        return policy->min;

    core = READ_ONCE(sge_array[policy->cpu][SD_LEVEL0]);
    cluster = READ_ONCE(sge_array[policy->cpu][SD_LEVEL1]);
    if (unlikely(!core || !core->cap_states || !core->nr_cap_states ||
                 !policy->freq_table)) {
        pr_warn_once("missing DTS energy model or OPP table: safe maximum\n");
        return policy->max;
    }

    for (i = 0; i < core->nr_cap_states; i++)
        max_cap = max(max_cap, (unsigned long)core->cap_states[i].cap);
    if (unlikely(!max_cap || !policy->cpuinfo.max_freq))
        return policy->max;

    /* Capacity headroom is a constraint. It is NOT a frequency formula. */
    required = (unsigned long)div64_u64(
                (u64)min(peak_load, EAGOV_LOAD_SCALE) * max_cap *
                EAGOV_CAPACITY_MARGIN_NUM +
                (u64)EAGOV_LOAD_SCALE * EAGOV_CAPACITY_MARGIN_DEN - 1,
                (u64)EAGOV_LOAD_SCALE * EAGOV_CAPACITY_MARGIN_DEN);
    required = clamp_val(required, 1UL, max_cap);

    core_idle = core->idle_states && core->nr_idle_states ?
                core->idle_states[0].power : 0;
    cluster_idle = cluster && cluster->idle_states &&
                   cluster->nr_idle_states ?
                   cluster->idle_states[0].power : 0;

    /*
     * Like A53 EGO's ego_find_energy_freq(), walk driver-supported
     * frequencies and compare the cost to execute the same workload.
     * The frequency-to-capacity conversion is the Linux 4.4 fallback
     * for Exynos1280's et_freq_to_cap(), using Exynos8895's DTS caps.
     */
    cpufreq_for_each_valid_entry(opp, policy->freq_table) {
        const struct capacity_state *core_state = NULL;
        const struct capacity_state *cluster_state = NULL;
        unsigned long opp_cap, core_dynamic, cluster_dynamic;
        unsigned int freq = opp->frequency;
        u64 energy;

        if (freq < policy->min || freq > policy->max)
            continue;

        opp_cap = (unsigned long)div64_u64((u64)max_cap * freq,
                                            policy->cpuinfo.max_freq);
        opp_cap = clamp_val(opp_cap, 1UL, max_cap);
        if (opp_cap < required)
            continue;

        for (i = 0; i < core->nr_cap_states; i++) {
            if (core->cap_states[i].cap >= opp_cap) {
                core_state = &core->cap_states[i];
                break;
            }
        }
        if (!core_state)
            core_state = &core->cap_states[core->nr_cap_states - 1];

        /*
         * Core idle power is charged for every member of the policy;
         * dynamic power scales with SUM of active CPU work fractions.
         */
        core_dynamic = core_state->power > core_idle ?
                       core_state->power - core_idle : 0;
        energy = (u64)core_idle * cpumask_weight(policy->cpus) *
                 EAGOV_LOAD_SCALE;
        energy += div64_u64(
                    (u64)core_dynamic * total_load * max_cap, opp_cap);

        /* Shared cluster idle cost only ONCE; dynamic cost at peak. */
        if (cluster && cluster->cap_states && cluster->nr_cap_states) {
            for (i = 0; i < cluster->nr_cap_states; i++) {
                if (cluster->cap_states[i].cap >= opp_cap) {
                    cluster_state = &cluster->cap_states[i];
                    break;
                }
            }
            if (!cluster_state)
                cluster_state =
                    &cluster->cap_states[cluster->nr_cap_states - 1];

            cluster_dynamic = cluster_state->power > cluster_idle ?
                              cluster_state->power - cluster_idle : 0;
            energy += (u64)cluster_idle * EAGOV_LOAD_SCALE;
            energy += div64_u64(
                        (u64)cluster_dynamic * peak_load * max_cap,
                        opp_cap);
        }

        if (!found || energy < best_energy ||
            (energy == best_energy && freq < best_freq)) {
            best_energy = energy;
            best_freq = freq;
            found = true;
        }
    }

    /* The PM/QoS constrained policy may have no feasible energy OPP. */
    return found ? best_freq : policy->max;
}

static inline bool use_pelt(void)
{
#ifdef CONFIG_SCHED_WALT
	return (!sysctl_sched_use_walt_cpu_util || walt_disabled);
#else
	return true;
#endif
}

static void eagov_get_util(unsigned long *util, unsigned long *max, u64 time)
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

static void eagov_set_iowait_boost(struct eagov_cpu *sg_cpu, u64 time,
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

static void eagov_iowait_boost(struct eagov_cpu *sg_cpu, unsigned long *util,
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
static bool eagov_cpu_is_busy(struct eagov_cpu *sg_cpu)
{
	unsigned long idle_calls = tick_nohz_get_idle_calls();
	bool ret = idle_calls == sg_cpu->saved_idle_calls;

	sg_cpu->saved_idle_calls = idle_calls;
	return ret;
}
#else
static inline bool eagov_cpu_is_busy(struct eagov_cpu *sg_cpu) { return false; }
#endif /* CONFIG_NO_HZ_COMMON */

static void eagov_update_single(struct update_util_data *hook, u64 time,
				unsigned int flags)
{
	struct eagov_cpu *sg_cpu = container_of(hook, struct eagov_cpu, update_util);
	struct eagov_policy *sg_policy = sg_cpu->sg_policy;
	struct cpufreq_policy *policy = sg_policy->policy;
	unsigned long util, max;
	unsigned int next_f;
	bool busy;

	eagov_set_iowait_boost(sg_cpu, time, flags);
	sg_cpu->last_update = time;

	if (!eagov_should_update_freq(sg_policy, time))
		return;

	busy = eagov_cpu_is_busy(sg_cpu);

	if (flags & SCHED_CPUFREQ_DL) {
		next_f = policy->cpuinfo.max_freq;
	} else {
		eagov_get_util(&util, &max, time);
		eagov_iowait_boost(sg_cpu, &util, &max);
		/* Let the energy model choose the OPP for this CPU workload. */
		util = eagov_util_to_load(util, max);
		next_f = eagov_energy_model_freq(sg_policy, util, util);
		/*
		 * Do not reduce the frequency if the CPU has not been idle
		 * recently, as the reduction is likely to be premature then.
		 */
		if (busy && next_f < sg_policy->next_freq)
			next_f = sg_policy->next_freq;
	}
	/* Serialize single-CPU slow-path updates with the worker too. */
	if (policy->fast_switch_enabled) {
		eagov_update_commit(sg_policy, time, next_f);
	} else {
		raw_spin_lock(&sg_policy->update_lock);
		eagov_update_commit(sg_policy, time, next_f);
		raw_spin_unlock(&sg_policy->update_lock);
	}
}

static unsigned int eagov_next_freq_shared(struct eagov_cpu *sg_cpu, u64 time)
{
    struct eagov_policy *sg_policy = sg_cpu->sg_policy;
    struct cpufreq_policy *policy = sg_policy->policy;
    unsigned long peak_load = 0, total_load = 0;
    unsigned int j;

    for_each_cpu(j, policy->cpus) {
        struct eagov_cpu *j_sg_cpu = &per_cpu(eagov_cpu, j);
        unsigned long j_util, j_max, j_load;
        s64 delta_ns;

        /* Exclude stale tasks when estimating the next window's work. */
        delta_ns = time - j_sg_cpu->last_update;
        if (delta_ns > stale_ns) {
            j_sg_cpu->iowait_boost = 0;
            j_sg_cpu->iowait_boost_pending = false;
            continue;
        }
        if (j_sg_cpu->flags & SCHED_CPUFREQ_DL)
            return policy->max;

        j_util = j_sg_cpu->util;
        j_max = j_sg_cpu->max;
        eagov_iowait_boost(j_sg_cpu, &j_util, &j_max);
        j_load = eagov_util_to_load(j_util, j_max);
        peak_load = max(peak_load, j_load);
        total_load += j_load;
    }

    return eagov_energy_model_freq(sg_policy, peak_load, total_load);
}

static void eagov_update_shared(struct update_util_data *hook, u64 time,
				unsigned int flags)
{
	struct eagov_cpu *sg_cpu = container_of(hook, struct eagov_cpu, update_util);
	struct eagov_policy *sg_policy = sg_cpu->sg_policy;
	unsigned long util, max;
	unsigned int next_f;

	eagov_get_util(&util, &max, time);

	raw_spin_lock(&sg_policy->update_lock);

	sg_cpu->util = util;
	sg_cpu->max = max;
	sg_cpu->flags = flags;

	eagov_set_iowait_boost(sg_cpu, time, flags);
	sg_cpu->last_update = time;

	if (eagov_should_update_freq(sg_policy, time)) {
		if (flags & SCHED_CPUFREQ_DL)
			next_f = sg_policy->policy->cpuinfo.max_freq;
		else
			next_f = eagov_next_freq_shared(sg_cpu, time);

		eagov_update_commit(sg_policy, time, next_f);
	}

	raw_spin_unlock(&sg_policy->update_lock);
}

static void eagov_work(struct kthread_work *work)
{
	struct eagov_policy *sg_policy = container_of(work, struct eagov_policy, work);
	unsigned int freq;
	unsigned long flags;
	int attempt;

	/*
	 * Keep work_in_progress set until the current target completes.
	 * Drain at most two requests so an endless UI utilization stream
	 * cannot monopolize the cpufreq kthread.  If more updates arrive,
	 * schedule a fresh work item instead of losing the latest target.
	 */
	mutex_lock(&sg_policy->work_lock);
	for (attempt = 0; attempt < 2; attempt++) {
		raw_spin_lock_irqsave(&sg_policy->update_lock, flags);
		freq = sg_policy->next_freq;
		raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);

		__cpufreq_driver_target(sg_policy->policy, freq,
					CPUFREQ_RELATION_L);

		raw_spin_lock_irqsave(&sg_policy->update_lock, flags);
		if (sg_policy->next_freq == freq) {
			sg_policy->work_in_progress = false;
			raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);
			break;
		}
		if (attempt == 1) {
			/*
			 * The currently executing kthread_work has already
			 * left its queue.  The IRQ work will enqueue it again
			 * when another frequency target is pending.
			 */
			irq_work_queue(&sg_policy->irq_work);
		}
		raw_spin_unlock_irqrestore(&sg_policy->update_lock, flags);
	}
	mutex_unlock(&sg_policy->work_lock);
}

static void eagov_irq_work(struct irq_work *irq_work)
{
	struct eagov_policy *sg_policy;

	sg_policy = container_of(irq_work, struct eagov_policy, irq_work);

	queue_kthread_work(&sg_policy->worker, &sg_policy->work);
}

/************************** sysfs interface ************************/

static struct eagov_tunables *global_tunables;
static DEFINE_MUTEX(global_tunables_lock);

static inline struct eagov_tunables *to_eagov_tunables(struct gov_attr_set *attr_set)
{
	return container_of(attr_set, struct eagov_tunables, attr_set);
}

static DEFINE_MUTEX(min_rate_lock);

static void update_min_rate_limit_us(struct eagov_policy *sg_policy)
{
	mutex_lock(&min_rate_lock);
	sg_policy->min_rate_limit_ns = min(sg_policy->up_rate_delay_ns,
					   sg_policy->down_rate_delay_ns);
	mutex_unlock(&min_rate_lock);
}

static ssize_t up_rate_limit_us_show(struct gov_attr_set *attr_set, char *buf)
{
	struct eagov_tunables *tunables = to_eagov_tunables(attr_set);

	return sprintf(buf, "%u\n", tunables->up_rate_limit_us);
}

static ssize_t down_rate_limit_us_show(struct gov_attr_set *attr_set, char *buf)
{
	struct eagov_tunables *tunables = to_eagov_tunables(attr_set);

	return sprintf(buf, "%u\n", tunables->down_rate_limit_us);
}

static ssize_t up_rate_limit_us_store(struct gov_attr_set *attr_set,
				      const char *buf, size_t count)
{
	struct eagov_tunables *tunables = to_eagov_tunables(attr_set);
	struct eagov_policy *sg_policy;
	unsigned int rate_limit_us;

	if (kstrtouint(buf, 10, &rate_limit_us))
		return -EINVAL;

	tunables->up_rate_limit_us = rate_limit_us;

	list_for_each_entry(sg_policy, &attr_set->policy_list, tunables_hook) {
		sg_policy->up_rate_delay_ns = rate_limit_us * NSEC_PER_USEC;
		update_min_rate_limit_us(sg_policy);
	}

	return count;
}

static ssize_t down_rate_limit_us_store(struct gov_attr_set *attr_set,
					const char *buf, size_t count)
{
	struct eagov_tunables *tunables = to_eagov_tunables(attr_set);
	struct eagov_policy *sg_policy;
	unsigned int rate_limit_us;

	if (kstrtouint(buf, 10, &rate_limit_us))
		return -EINVAL;

	tunables->down_rate_limit_us = rate_limit_us;

	list_for_each_entry(sg_policy, &attr_set->policy_list, tunables_hook) {
		sg_policy->down_rate_delay_ns = rate_limit_us * NSEC_PER_USEC;
		update_min_rate_limit_us(sg_policy);
	}

	return count;
}

static struct governor_attr up_rate_limit_us = __ATTR_RW(up_rate_limit_us);
static struct governor_attr down_rate_limit_us = __ATTR_RW(down_rate_limit_us);

static struct attribute *eagov_attributes[] = {
	&up_rate_limit_us.attr,
	&down_rate_limit_us.attr,
	NULL
};

static struct kobj_type eagov_tunables_ktype = {
	.default_attrs = eagov_attributes,
	.sysfs_ops = &governor_sysfs_ops,
};

/********************** cpufreq governor interface *********************/
#ifndef CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYAWARE
static
#endif
struct cpufreq_governor cpufreq_gov_energy_aware;

static struct eagov_policy *eagov_policy_alloc(struct cpufreq_policy *policy)
{
	struct eagov_policy *sg_policy;

	sg_policy = kzalloc(sizeof(*sg_policy), GFP_KERNEL);
	if (!sg_policy)
		return NULL;

	sg_policy->policy = policy;
	raw_spin_lock_init(&sg_policy->update_lock);
	return sg_policy;
}

static void eagov_policy_free(struct eagov_policy *sg_policy)
{
	kfree(sg_policy);
}

static int eagov_kthread_create(struct eagov_policy *sg_policy)
{
	struct task_struct *thread;
	struct sched_param param = { .sched_priority = MAX_USER_RT_PRIO / 2 };
	struct cpufreq_policy *policy = sg_policy->policy;
	int ret;

	/* kthread only required for slow path */
	if (policy->fast_switch_enabled)
		return 0;

	init_kthread_work(&sg_policy->work, eagov_work);
	init_kthread_worker(&sg_policy->worker);
	thread = kthread_create(kthread_worker_fn, &sg_policy->worker,
				"eagov:%d",
				cpumask_first(policy->related_cpus));
	if (IS_ERR(thread)) {
		pr_err("failed to create eagov thread: %ld\n", PTR_ERR(thread));
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
	init_irq_work(&sg_policy->irq_work, eagov_irq_work);
	mutex_init(&sg_policy->work_lock);

	wake_up_process(thread);

	return 0;
}

static void eagov_kthread_stop(struct eagov_policy *sg_policy)
{
	/* kthread only required for slow path */
	if (sg_policy->policy->fast_switch_enabled)
		return;

	flush_kthread_worker(&sg_policy->worker);
	kthread_stop(sg_policy->thread);
	mutex_destroy(&sg_policy->work_lock);
}

static struct eagov_tunables *eagov_tunables_alloc(struct eagov_policy *sg_policy)
{
	struct eagov_tunables *tunables;

	tunables = kzalloc(sizeof(*tunables), GFP_KERNEL);
	if (tunables) {
		gov_attr_set_init(&tunables->attr_set, &sg_policy->tunables_hook);
		if (!have_governor_per_policy())
			global_tunables = tunables;
	}
	return tunables;
}

static void eagov_tunables_save(struct cpufreq_policy *policy,
		struct eagov_tunables *tunables)
{
	int cpu;
	struct eagov_tunables *cached = per_cpu(cached_tunables, policy->cpu);

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

static void eagov_tunables_free(struct eagov_tunables *tunables)
{
	if (!have_governor_per_policy())
		global_tunables = NULL;

	kfree(tunables);
}

static void eagov_tunables_restore(struct cpufreq_policy *policy)
{
	struct eagov_policy *sg_policy = policy->governor_data;
	struct eagov_tunables *tunables = sg_policy->tunables;
	struct eagov_tunables *cached = per_cpu(cached_tunables, policy->cpu);

	if (!cached)
		return;

	tunables->up_rate_limit_us = cached->up_rate_limit_us;
	tunables->down_rate_limit_us = cached->down_rate_limit_us;
	sg_policy->up_rate_delay_ns =
		tunables->up_rate_limit_us * NSEC_PER_USEC;
	sg_policy->down_rate_delay_ns =
		tunables->down_rate_limit_us * NSEC_PER_USEC;
	sg_policy->min_rate_limit_ns = min(sg_policy->up_rate_delay_ns,
					   sg_policy->down_rate_delay_ns);
}

static int eagov_init(struct cpufreq_policy *policy)
{
	struct eagov_policy *sg_policy;
	struct eagov_tunables *tunables;
	int ret = 0;

	/* State should be equivalent to EXIT */
	if (policy->governor_data)
		return -EBUSY;

	cpufreq_enable_fast_switch(policy);

	sg_policy = eagov_policy_alloc(policy);
	if (!sg_policy) {
		ret = -ENOMEM;
		goto disable_fast_switch;
	}

	ret = eagov_kthread_create(sg_policy);
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

	tunables = eagov_tunables_alloc(sg_policy);
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
		 * short 2.5 ms response window, then release a stale high OPP after
		 * 8 ms.  This keeps UI bursts responsive without pinning the Exynos M2
		 * cluster at an overclocked OPP between frames.
		 */
		tunables->up_rate_limit_us = EAGOV_DEFAULT_UP_RATE_LIMIT_US;
		tunables->down_rate_limit_us = EAGOV_DEFAULT_DOWN_RATE_LIMIT_US;
	}

	policy->governor_data = sg_policy;
	sg_policy->tunables = tunables;
	stale_ns = walt_ravg_window + (walt_ravg_window >> 3);

	eagov_tunables_restore(policy);

	ret = kobject_init_and_add(&tunables->attr_set.kobj, &eagov_tunables_ktype,
				   get_governor_parent_kobj(policy), "%s",
				   cpufreq_gov_energy_aware.name);
	if (ret)
		goto fail;

out:
	mutex_unlock(&global_tunables_lock);
	return 0;

fail:
	policy->governor_data = NULL;
	eagov_tunables_free(tunables);

stop_kthread:
	eagov_kthread_stop(sg_policy);

free_sg_policy:
	mutex_unlock(&global_tunables_lock);

	eagov_policy_free(sg_policy);

disable_fast_switch:
	cpufreq_disable_fast_switch(policy);

	pr_err("initialization failed (error %d)\n", ret);
	return ret;
}

static int eagov_exit(struct cpufreq_policy *policy)
{
	struct eagov_policy *sg_policy = policy->governor_data;
	struct eagov_tunables *tunables = sg_policy->tunables;
	unsigned int count;

	mutex_lock(&global_tunables_lock);

	count = gov_attr_set_put(&tunables->attr_set, &sg_policy->tunables_hook);
	policy->governor_data = NULL;
	if (!count) {
		eagov_tunables_save(policy, tunables);
		eagov_tunables_free(tunables);
	}

	mutex_unlock(&global_tunables_lock);

	eagov_kthread_stop(sg_policy);
	eagov_policy_free(sg_policy);

	cpufreq_disable_fast_switch(policy);
	return 0;
}

static int eagov_start(struct cpufreq_policy *policy)
{
	struct eagov_policy *sg_policy = policy->governor_data;
	unsigned int cpu;

	sg_policy->up_rate_delay_ns =
		sg_policy->tunables->up_rate_limit_us * NSEC_PER_USEC;
	sg_policy->down_rate_delay_ns =
		sg_policy->tunables->down_rate_limit_us * NSEC_PER_USEC;
	update_min_rate_limit_us(sg_policy);
	sg_policy->last_freq_update_time = 0;
	sg_policy->next_freq = 0;
	sg_policy->work_in_progress = false;
	sg_policy->need_freq_update = false;

	for_each_cpu(cpu, policy->cpus) {
		struct eagov_cpu *sg_cpu = &per_cpu(eagov_cpu, cpu);

		memset(sg_cpu, 0, sizeof(*sg_cpu));
		sg_cpu->sg_policy = sg_policy;
		sg_cpu->flags = SCHED_CPUFREQ_DL;
		sg_cpu->iowait_boost_max = policy->cpuinfo.max_freq;
	}

	for_each_cpu(cpu, policy->cpus) {
		struct eagov_cpu *sg_cpu = &per_cpu(eagov_cpu, cpu);

		cpufreq_add_update_util_hook(cpu, &sg_cpu->update_util,
					     policy_is_shared(policy) ?
							eagov_update_shared :
							eagov_update_single);
	}
	return 0;
}

static int eagov_stop(struct cpufreq_policy *policy)
{
	struct eagov_policy *sg_policy = policy->governor_data;
	unsigned int cpu;

	for_each_cpu(cpu, policy->cpus)
		cpufreq_remove_update_util_hook(cpu);

	synchronize_sched();

	if (!policy->fast_switch_enabled) {
		irq_work_sync(&sg_policy->irq_work);
		kthread_cancel_work_sync(&sg_policy->work);
	}
	return 0;
}

static int eagov_limits(struct cpufreq_policy *policy)
{
	struct eagov_policy *sg_policy = policy->governor_data;

	if (!policy->fast_switch_enabled) {
		mutex_lock(&sg_policy->work_lock);
		cpufreq_policy_apply_limits(policy);
		mutex_unlock(&sg_policy->work_lock);
	}

	sg_policy->need_freq_update = true;

	return 0;
}

static int cpufreq_energy_aware_cb(struct cpufreq_policy *policy,
				unsigned int event)
{
	switch(event) {
	case CPUFREQ_GOV_POLICY_INIT:
		return eagov_init(policy);
	case CPUFREQ_GOV_POLICY_EXIT:
		return eagov_exit(policy);
	case CPUFREQ_GOV_START:
		return eagov_start(policy);
	case CPUFREQ_GOV_STOP:
		return eagov_stop(policy);
	case CPUFREQ_GOV_LIMITS:
		return eagov_limits(policy);
	default:
		BUG();
	}
}

#ifndef CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYAWARE
static
#endif
struct cpufreq_governor cpufreq_gov_energy_aware = {
	.name = "energy_aware",
	.governor = cpufreq_energy_aware_cb,
	.owner = THIS_MODULE,
};

static int __init eagov_register(void)
{
	return cpufreq_register_governor(&cpufreq_gov_energy_aware);
}
fs_initcall(eagov_register);
