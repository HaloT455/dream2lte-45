/*
 * Exynos8895 CPUFreq governor driven by discrete energy states.
 *
 * Copyright (C) 2016, Intel Corporation
 * Original scheduler/CPUFreq interface: Rafael J. Wysocki
 * Copyright (C) 2021, Samsung Electronic Corporation
 * A53 EGO search/idle-time mechanism backported for ALice / Exynos8895.
 * Licensed under the GNU General Public License version 2.
 */
#define pr_fmt(fmt) "energy_aware: " fmt

#include <linux/cpufreq.h>
#include <linux/cpuidle.h>
#include <linux/cpu.h>
#include <linux/pm_opp.h>
#include <linux/rcupdate.h>
#include <trace/events/power.h>
#include <linux/kthread.h>
#include <linux/math64.h>
#include <linux/of.h>
#include <linux/pm_qos.h>
#include <linux/sched_energy.h>
#include <linux/slab.h>

#include "sched.h"
#include "energy_aware_model.h"
#include "energy_aware_oc.h"
#include "energy_aware_idle.h"

unsigned long boosted_cpu_util(int cpu);

struct eagov_policy {
	struct cpufreq_policy *policy;
	unsigned int qos_min_class;
	unsigned int qos_max_class;
	struct eagov_energy_model model;
	/* Native Samsung DTS entries are exact; later OC power is estimated. */
	unsigned int nr_native_states;
	struct gov_attr_set attr_set;
	struct list_head attr_hook;
	raw_spinlock_t lock;
	struct mutex work_lock;
	struct irq_work irq_work;
	struct kthread_work work;
	struct kthread_worker worker;
	struct task_struct *thread;
	unsigned int target_state;
	unsigned int applied_state;
	unsigned long long target_energy;
	s64 power_delta;
	bool enabled;
	bool queued;
};

struct eagov_cpu {
	struct update_util_data hook;
	struct eagov_policy *policy;
	u64 time;
	unsigned int util;
	bool valid;
};

static DEFINE_PER_CPU(struct eagov_cpu, eagov_cpus);

struct ego_idle_cpu {
	raw_spinlock_t lock;
	struct ego_idle_history history;
};

static DEFINE_PER_CPU(struct ego_idle_cpu, ego_idle_cpus);

/* Native 4.4 replacement for A53 MLT CLKOFF/PWROFF event accounting. */
static void ego_idle_transition(void *unused, unsigned int state,
				unsigned int cpu)
{
	struct ego_idle_cpu *idle = &per_cpu(ego_idle_cpus, cpu);
	unsigned long flags;
	int next;

	if (state == (unsigned int)PWR_EVENT_EXIT)
		next = EGO_IDLE_RUNNING;
	else
		next = state ? EGO_IDLE_PWROFF : EGO_IDLE_CLKOFF;
	raw_spin_lock_irqsave(&idle->lock, flags);
	ego_idle_update(&idle->history, sched_clock_cpu(cpu), next);
	raw_spin_unlock_irqrestore(&idle->lock, flags);
}

/* A53 ego_compute_cpu_idle_ratio(), using eight native 4 ms periods. */
static unsigned int ego_compute_cpu_idle_ratio(unsigned int cpu)
{
	struct ego_idle_cpu *idle = &per_cpu(ego_idle_cpus, cpu);
	unsigned long flags;
	unsigned int ratio;

	raw_spin_lock_irqsave(&idle->lock, flags);
	ego_idle_update(&idle->history, sched_clock_cpu(cpu),
			idle->history.initialized ? idle->history.state :
			EGO_IDLE_RUNNING);
	ratio = ego_idle_clkoff_ratio(&idle->history);
	raw_spin_unlock_irqrestore(&idle->lock, flags);
	return ratio;
}

/* Resolve the same native Samsung QoS classes used by Exynos ACME. */
static int eagov_init_qos(struct eagov_policy *ea)
{
	struct device_node *node;
	const char *cpus;
	cpumask_t mask;
	int ret;

	for_each_node_by_type(node, "cpufreq-domain") {
		if (of_property_read_string(node, "sibling-cpus", &cpus) ||
		    cpulist_parse(cpus, &mask) ||
		    !cpumask_test_cpu(ea->policy->cpu, &mask))
			continue;
		ret = of_property_read_u32(node, "pm_qos-min-class",
					   &ea->qos_min_class);
		ret |= of_property_read_u32(node, "pm_qos-max-class",
					    &ea->qos_max_class);
		of_node_put(node);
		if (ret || !ea->qos_min_class || !ea->qos_max_class ||
		    ea->qos_min_class >= PM_QOS_NUM_CLASSES ||
		    ea->qos_max_class >= PM_QOS_NUM_CLASSES)
			return -EINVAL;
		return 0;
	}
	return -ENODEV;
}

/* Native replacement for A53's external fclamp/EMS frequency limits. */
static void eagov_qos_range(struct eagov_policy *ea, unsigned int *low,
			    unsigned int *high)
{
	struct cpufreq_policy *policy = ea->policy;
	int qos_min = pm_qos_request(ea->qos_min_class);
	int qos_max = pm_qos_request(ea->qos_max_class);

	*low = policy->min;
	*high = policy->max;
	if (qos_min < 0 || qos_max < 0)
		return;
	*low = clamp_val((unsigned int)qos_min, policy->min, policy->max);
	*high = clamp_val((unsigned int)qos_max, policy->min, policy->max);
}

/* ACME registers the real CAL/ASV voltage for each supported OPP. */
static unsigned int eagov_opp_voltage(struct cpufreq_policy *policy,
				      unsigned int frequency)
{
	struct device *dev = get_cpu_device(cpumask_first(policy->cpus));
	struct dev_pm_opp *opp;
	unsigned long uv = 0;

	if (!dev)
		return 0;

	/* OPP pointers remain valid ONLY while holding rcu_read_lock(). */
	rcu_read_lock();
	opp = dev_pm_opp_find_freq_exact(dev,
					(unsigned long)frequency * 1000UL, true);
	if (!IS_ERR(opp))
		uv = dev_pm_opp_get_voltage(opp);
	rcu_read_unlock();
	return uv > (~0U) ? 0 : (unsigned int)uv;
}

/*
 * Extend the model ONLY with valid ACME/CAL OPPs above the native DTS
 * table. Missing or invalid ASV voltage causes initialization to FAIL,
 * never an invented OC OPP or fabricated "Samsung measured" power.
 *
 * The native busy power includes chip-specific effects not measured at
 * OC frequencies. P ~ f*V^2 is therefore an engineering estimate only.
 */
static int eagov_append_oc_states(struct eagov_policy *ea,
				   unsigned int allocated)
{
	struct cpufreq_policy *policy = ea->policy;
	struct eagov_energy_model *model = &ea->model;
	const struct eagov_energy_state *base;
	unsigned int base_uv, prev_freq, next, nr = ea->nr_native_states;
	struct cpufreq_frequency_table *opp;

	if (!nr)
		return -EINVAL;
	base = &model->states[nr - 1];
	prev_freq = base->frequency;
	if (policy->cpuinfo.max_freq <= prev_freq)
		return 0;

	base_uv = eagov_opp_voltage(policy, base->frequency);
	if (!base_uv)
		return -ENODEV;

	while (prev_freq < policy->cpuinfo.max_freq) {
		struct eagov_energy_state *state;
		unsigned int uv, core_power, cluster_power, capacity;

		/* ACME's CAL table may be descending: choose next ascending. */
		next = ~0U;
		cpufreq_for_each_valid_entry(opp, policy->freq_table) {
			if (opp->frequency > prev_freq &&
			    opp->frequency <= policy->cpuinfo.max_freq &&
			    opp->frequency < next)
				next = opp->frequency;
		}
		if (next == ~0U)
			break;
		if (nr >= allocated)
			return -EOVERFLOW;

		uv = eagov_opp_voltage(policy, next);
		core_power = eagov_estimate_oc_power(base->core_power,
			    base->frequency, base_uv, next, uv);
		cluster_power = eagov_estimate_oc_power(base->cluster_power,
			    base->frequency, base_uv, next, uv);
		capacity = eagov_estimate_oc_capacity(base->capacity,
			    base->frequency, next);
		if (!uv || !core_power || !cluster_power || !capacity)
			return -EINVAL;

		state = &model->states[nr];
		state->frequency = next;
		state->capacity = capacity;
		state->core_power = max(core_power,
				model->states[nr - 1].core_power + 1);
		state->cluster_power = max(cluster_power,
				model->states[nr - 1].cluster_power + 1);
		nr++;
		prev_freq = next;
	}

	if (prev_freq < policy->cpuinfo.max_freq)
		return -EINVAL;
	model->nr_states = nr;
	pr_info("CPU%u: %u native DTS states + %u CAL/ASV OC states (estimated power)\\n",
		policy->cpu, ea->nr_native_states, nr - ea->nr_native_states);
	return 0;
}

/* Every Samsung native state is bound to a concrete frequency-data row. */
static int eagov_build_model(struct eagov_policy *ea)
{
	struct cpufreq_policy *policy = ea->policy;
	const struct sched_group_energy *core, *cluster;
	struct device_node *cpu_node, *cost_node;
	struct cpufreq_frequency_table *opp;
	unsigned int previous_freq = 0;
	unsigned int i, j, nr = 0, allocated = 0;
	int ret = -EINVAL;

	core = sge_array[policy->cpu][SD_LEVEL0];
	cluster = sge_array[policy->cpu][SD_LEVEL1];
	if (!core || !cluster || !core->nr_cap_states ||
	    core->nr_cap_states != cluster->nr_cap_states ||
	    !core->cap_states || !cluster->cap_states || !policy->freq_table)
		return -EINVAL;

	cpu_node = of_get_cpu_node(policy->cpu, NULL);
	if (!cpu_node)
		return -EINVAL;
	cost_node = of_parse_phandle(cpu_node, "sched-energy-costs", SD_LEVEL0);
	of_node_put(cpu_node);
	if (!cost_node)
		return -EINVAL;
	if (of_property_count_u32_elems(cost_node, "frequency-data") !=
	    core->nr_cap_states)
		goto put_node;

	cpufreq_for_each_valid_entry(opp, policy->freq_table)
		allocated++;
	allocated = max(allocated, (unsigned int)core->nr_cap_states);
	ea->model.states = kcalloc(allocated, sizeof(*ea->model.states),
				   GFP_KERNEL);
	if (!ea->model.states) {
		ret = -ENOMEM;
		goto put_node;
	}

	for (i = 0; i < core->nr_cap_states; i++) {
		struct eagov_energy_state *state = &ea->model.states[nr];
		u32 frequency;
		bool supported = false;

		if (of_property_read_u32_index(cost_node, "frequency-data", i,
					       &frequency) ||
		    frequency <= previous_freq || !core->cap_states[i].cap ||
		    core->cap_states[i].cap > SCHED_CAPACITY_SCALE ||
		    (i && core->cap_states[i].cap <=
			  core->cap_states[i - 1].cap))
			goto free_states;
		previous_freq = frequency;
		for (j = 0; j < cluster->nr_cap_states; j++)
			if (cluster->cap_states[j].cap ==
			    core->cap_states[i].cap)
				break;
		if (j == cluster->nr_cap_states)
			goto free_states;

		cpufreq_for_each_valid_entry(opp, policy->freq_table)
			if (opp->frequency == frequency) {
				supported = true;
				break;
			}
		if (!supported)
			continue;

		state->frequency = frequency;
		state->capacity = core->cap_states[i].cap;
		state->core_power = core->cap_states[i].power;
		state->cluster_power = cluster->cap_states[j].power;
		nr++;
	}
	if (!nr || policy->cpuinfo.min_freq < ea->model.states[0].frequency ||
	    ea->model.states[nr - 1].frequency != previous_freq)
		goto free_states;

	ea->nr_native_states = nr;
	ea->model.nr_states = nr;
	ret = eagov_append_oc_states(ea, allocated);
	if (ret)
		goto free_states;

	ea->model.core_idle = core->nr_idle_states && core->idle_states ?
				core->idle_states[0].power : 0;
	ea->model.core_pwroff = core->nr_idle_states > 1 && core->idle_states ?
				  core->idle_states[1].power : 0;
	ea->model.cluster_idle =
		cluster->nr_idle_states && cluster->idle_states ?
		cluster->idle_states[0].power : 0;
	ret = 0;
	goto put_node;

free_states:
	kfree(ea->model.states);
	ea->model.states = NULL;
	ea->model.nr_states = 0;
put_node:
	of_node_put(cost_node);
	return ret;
}

static unsigned int eagov_read_util(struct eagov_policy *ea, u64 time,
				    unsigned int flags)
{
	struct rq *rq = cpu_rq(smp_processor_id());
	unsigned int capacity =
		ea->model.states[ea->model.nr_states - 1].capacity;
	unsigned long util, rt;
	s64 delta;
	bool pelt = true;

	if (flags & SCHED_CPUFREQ_DL)
		return capacity;
#ifdef CONFIG_SCHED_WALT
	pelt = !sysctl_sched_use_walt_cpu_util || walt_disabled;
#endif
	util = boosted_cpu_util(smp_processor_id());
	if (pelt) {
		sched_avg_update(rq);
		delta = max_t(s64, time - rq->age_stamp, 0);
		rt = div64_u64(rq->rt_avg, sched_avg_period() + delta);
		util += (rt * capacity) >> SCHED_CAPACITY_SHIFT;
	}
	return min_t(unsigned long, util, capacity);
}

static u64 eagov_sample_window(void)
{
#ifdef CONFIG_SCHED_WALT
	if (!walt_disabled && sysctl_sched_use_walt_cpu_util)
		return (u64)walt_ravg_window + (walt_ravg_window >> 3);
#endif
	return 2 * TICK_NSEC;
}

static u64 eagov_busy_power(struct eagov_policy *ea, unsigned int index)
{
	struct eagov_energy_state *state = &ea->model.states[index];

	return (u64)state->core_power * cpumask_weight(ea->policy->cpus) +
		state->cluster_power;
}

/* Called under ea->lock. The energy model is the only decision path. */
static void eagov_request(struct eagov_policy *ea, u64 time)
{
	struct eagov_energy_choice choice;
	struct ego_cpu_work cpus[NR_CPUS];
	struct ego_workload work = { .cpus = cpus };
	unsigned int cpu, low, high;
	s64 window = eagov_sample_window();

	for_each_cpu(cpu, ea->policy->cpus) {
		struct eagov_cpu *sample = &per_cpu(eagov_cpus, cpu);

		struct ego_cpu_work *input = &cpus[work.nr_cpus++];

		input->util = !sample->valid ||
			(s64)(time - sample->time) > window ? 0 : sample->util;
		input->clkoff_ratio = ego_compute_cpu_idle_ratio(cpu);
		work.peak = max(work.peak, input->util);
	}
	eagov_qos_range(ea, &low, &high);
	choice = ego_find_energy_freq(&ea->model, &work, low, high);
	/* A conflicting QoS floor cannot defeat a thermal/QoS ceiling. */
	if (choice.state == EAGOV_NO_STATE)
		choice = ego_find_energy_freq(&ea->model, &work,
					    ea->policy->min, high);
	if (WARN_ON_ONCE(choice.state == EAGOV_NO_STATE))
		return;

	/* QoS can change the hardware OPP outside this governor's worker. */
	if (!ea->queued && ea->applied_state != EAGOV_NO_STATE &&
	    ea->policy->cur != ea->model.states[ea->applied_state].frequency)
		ea->applied_state = EAGOV_NO_STATE;
	ea->target_energy = choice.energy;
	ea->target_state = choice.state;
	if (ea->enabled && !ea->queued && ea->applied_state != choice.state) {
		ea->queued = true;
		irq_work_queue(&ea->irq_work);
	}
}

static void eagov_update(struct update_util_data *hook, u64 time,
			 unsigned int flags)
{
	struct eagov_cpu *sample = container_of(hook, struct eagov_cpu, hook);
	struct eagov_policy *ea = sample->policy;
	unsigned int util = eagov_read_util(ea, time, flags);

	raw_spin_lock(&ea->lock);
	sample->util = util;
	sample->time = time;
	sample->valid = true;
	if (ea->enabled)
		eagov_request(ea, time);
	raw_spin_unlock(&ea->lock);
}

/* The sleeping Exynos driver is transport; it never selects an energy step. */
static void eagov_work(struct kthread_work *work)
{
	struct eagov_policy *ea = container_of(work, struct eagov_policy, work);
	unsigned int state, frequency, previous;
	unsigned long flags;
	int attempt, ret;

	mutex_lock(&ea->work_lock);
	for (attempt = 0; attempt < 2; attempt++) {
		raw_spin_lock_irqsave(&ea->lock, flags);
		state = ea->target_state;
		if (!ea->enabled || state == EAGOV_NO_STATE) {
			ea->queued = false;
			raw_spin_unlock_irqrestore(&ea->lock, flags);
			break;
		}
		frequency = ea->model.states[state].frequency;
		previous = ea->applied_state;
		raw_spin_unlock_irqrestore(&ea->lock, flags);

		ret = __cpufreq_driver_target(ea->policy, frequency,
					      CPUFREQ_RELATION_L);

		raw_spin_lock_irqsave(&ea->lock, flags);
		/* QoS may clamp the driver: acknowledge only an applied OPP. */
		ea->applied_state = !ret && ea->policy->cur == frequency ?
				    state : EAGOV_NO_STATE;
		if (ea->applied_state != EAGOV_NO_STATE && previous != state)
			ea->power_delta = previous == EAGOV_NO_STATE ? 0 :
				(s64)eagov_busy_power(ea, state) -
				(s64)eagov_busy_power(ea, previous);
		if (ret || !ea->enabled || ea->target_state == state) {
			ea->queued = false;
			raw_spin_unlock_irqrestore(&ea->lock, flags);
			break;
		}
		if (attempt == 1)
			irq_work_queue(&ea->irq_work);
		raw_spin_unlock_irqrestore(&ea->lock, flags);
	}
	mutex_unlock(&ea->work_lock);
}

static void eagov_irq_work(struct irq_work *irq)
{
	struct eagov_policy *ea =
		container_of(irq, struct eagov_policy, irq_work);

	queue_kthread_work(&ea->worker, &ea->work);
}

static struct eagov_policy *eagov_from_attrs(struct gov_attr_set *set)
{
	return container_of(set, struct eagov_policy, attr_set);
}

static ssize_t idle_ratios_show(struct gov_attr_set *set, char *buf)
{
	struct eagov_policy *ea = eagov_from_attrs(set);
	unsigned int cpu;
	int len = 0;

	len += scnprintf(buf, PAGE_SIZE, "cpu clkoff pwroff (scale 1024)\n");
	for_each_cpu(cpu, ea->policy->cpus) {
		unsigned int ratio = ego_compute_cpu_idle_ratio(cpu);

		len += scnprintf(buf + len, PAGE_SIZE - len, "%u %u %u\n",
				 cpu, ratio, EAGOV_ENERGY_SCALE - ratio);
	}
	return len;
}

static ssize_t energy_step_show(struct gov_attr_set *set, char *buf)
{
	struct eagov_policy *ea = eagov_from_attrs(set);
	unsigned int state = READ_ONCE(ea->applied_state);

	return sprintf(buf, "%u\n", state == EAGOV_NO_STATE ? 0 : state + 1);
}

static ssize_t energy_delta_show(struct gov_attr_set *set, char *buf)
{
	struct eagov_policy *ea = eagov_from_attrs(set);

	return sprintf(buf, "%lld\n", (long long)READ_ONCE(ea->power_delta));
}

static ssize_t predicted_energy_show(struct gov_attr_set *set, char *buf)
{
	struct eagov_policy *ea = eagov_from_attrs(set);

	return sprintf(buf, "%llu\n", READ_ONCE(ea->target_energy));
}

static ssize_t energy_steps_show(struct gov_attr_set *set, char *buf)
{
	struct eagov_policy *ea = eagov_from_attrs(set);
	unsigned int i;
	int len = 0;
	u64 previous = 0;

	len += scnprintf(buf, PAGE_SIZE,
			 "step kHz capacity core cluster busy_power delta_power source\n");
	for (i = 0; i < ea->model.nr_states && len < PAGE_SIZE; i++) {
		struct eagov_energy_state *state = &ea->model.states[i];
		u64 power = eagov_busy_power(ea, i);

		len += scnprintf(buf + len, PAGE_SIZE - len,
				 "%u %u %u %u %u %llu %lld %s\n", i + 1,
				 state->frequency, state->capacity,
				 state->core_power, state->cluster_power,
				 (unsigned long long)power,
				 i ? (long long)(power - previous) : 0LL,
				 i < ea->nr_native_states ? "DTS" : "OC_EST");
		previous = power;
	}
	return len;
}

static struct governor_attr idle_ratios = __ATTR_RO(idle_ratios);
static struct governor_attr energy_step = __ATTR_RO(energy_step);
static struct governor_attr energy_delta = __ATTR_RO(energy_delta);
static struct governor_attr energy_steps = __ATTR_RO(energy_steps);
static struct governor_attr predicted_energy = __ATTR_RO(predicted_energy);
static struct attribute *eagov_attributes[] = {
	&idle_ratios.attr,
	&energy_step.attr,
	&energy_delta.attr,
	&energy_steps.attr,
	&predicted_energy.attr,
	NULL
};

static void eagov_release(struct kobject *kobj)
{
	struct gov_attr_set *set =
		container_of(kobj, struct gov_attr_set, kobj);
	struct eagov_policy *ea = eagov_from_attrs(set);

	kfree(ea->model.states);
	kfree(ea);
}

static struct kobj_type eagov_ktype = {
	.default_attrs = eagov_attributes,
	.sysfs_ops = &governor_sysfs_ops,
	.release = eagov_release,
};

static int eagov_init(struct cpufreq_policy *policy)
{
	struct sched_param param = { .sched_priority = MAX_USER_RT_PRIO / 2 };
	struct eagov_policy *ea;
	int ret;

	if (policy->governor_data)
		return -EBUSY;
	if (!have_governor_per_policy())
		return -EINVAL;
	ea = kzalloc(sizeof(*ea), GFP_KERNEL);
	if (!ea)
		return -ENOMEM;
	ea->policy = policy;
	ret = eagov_init_qos(ea);
	if (ret)
		goto free_policy;
	ret = eagov_build_model(ea);
	if (ret) {
		pr_err("CPU%u: complete frequency/capacity/power model required (%d)\n",
		       policy->cpu, ret);
		goto free_policy;
	}
	raw_spin_lock_init(&ea->lock);
	mutex_init(&ea->work_lock);
	init_irq_work(&ea->irq_work, eagov_irq_work);
	init_kthread_work(&ea->work, eagov_work);
	init_kthread_worker(&ea->worker);
	ea->thread = kthread_create(kthread_worker_fn, &ea->worker,
				    "energy_aware:%u", policy->cpu);
	if (IS_ERR(ea->thread)) {
		ret = PTR_ERR(ea->thread);
		goto free_model;
	}
	ret = sched_setscheduler_nocheck(ea->thread, SCHED_FIFO, &param);
	if (ret)
		goto stop_thread;
	kthread_bind_mask(ea->thread, policy->related_cpus);
	wake_up_process(ea->thread);

	ea->target_state = EAGOV_NO_STATE;
	ea->applied_state = EAGOV_NO_STATE;
	gov_attr_set_init(&ea->attr_set, &ea->attr_hook);
	ret = kobject_init_and_add(&ea->attr_set.kobj, &eagov_ktype,
				   get_governor_parent_kobj(policy),
				   "energy_aware");
	if (ret) {
		kthread_stop(ea->thread);
		mutex_destroy(&ea->work_lock);
		mutex_destroy(&ea->attr_set.update_lock);
		kobject_put(&ea->attr_set.kobj);
		return ret;
	}
	policy->governor_data = ea;
	return 0;

stop_thread:
	kthread_stop(ea->thread);
free_model:
	mutex_destroy(&ea->work_lock);
	kfree(ea->model.states);
free_policy:
	kfree(ea);
	return ret;
}

static int eagov_exit(struct cpufreq_policy *policy)
{
	struct eagov_policy *ea = policy->governor_data;

	flush_kthread_worker(&ea->worker);
	kthread_stop(ea->thread);
	mutex_destroy(&ea->work_lock);
	policy->governor_data = NULL;
	/* This embedded attr_set is freed by the kobject release callback. */
	mutex_destroy(&ea->attr_set.update_lock);
	kobject_put(&ea->attr_set.kobj);
	return 0;
}

static int eagov_start(struct cpufreq_policy *policy)
{
	struct eagov_policy *ea = policy->governor_data;
	unsigned int cpu;

	ea->target_state = EAGOV_NO_STATE;
	ea->applied_state = EAGOV_NO_STATE;
	ea->queued = false;
	ea->power_delta = 0;
	for_each_cpu(cpu, policy->cpus) {
		struct eagov_cpu *sample = &per_cpu(eagov_cpus, cpu);

		memset(sample, 0, sizeof(*sample));
		sample->policy = ea;
	}
	ea->enabled = true;
	for_each_cpu(cpu, policy->cpus) {
		struct eagov_cpu *sample = &per_cpu(eagov_cpus, cpu);

		cpufreq_add_update_util_hook(cpu, &sample->hook, eagov_update);
	}
	return 0;
}

static int eagov_stop(struct cpufreq_policy *policy)
{
	struct eagov_policy *ea = policy->governor_data;
	unsigned long flags;
	unsigned int cpu;

	for_each_cpu(cpu, policy->cpus)
		cpufreq_remove_update_util_hook(cpu);
	synchronize_sched();
	raw_spin_lock_irqsave(&ea->lock, flags);
	ea->enabled = false;
	raw_spin_unlock_irqrestore(&ea->lock, flags);
	irq_work_sync(&ea->irq_work);
	kthread_cancel_work_sync(&ea->work);
	return 0;
}

static int eagov_limits(struct cpufreq_policy *policy)
{
	struct eagov_policy *ea = policy->governor_data;
	unsigned long flags;

	mutex_lock(&ea->work_lock);
	cpufreq_policy_apply_limits(policy);
	raw_spin_lock_irqsave(&ea->lock, flags);
	ea->applied_state = EAGOV_NO_STATE;
	if (ea->enabled)
		eagov_request(ea, sched_clock_cpu(policy->cpu));
	raw_spin_unlock_irqrestore(&ea->lock, flags);
	mutex_unlock(&ea->work_lock);
	return 0;
}

static int cpufreq_energy_aware_cb(struct cpufreq_policy *policy,
				   unsigned int event)
{
	switch (event) {
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
		return -EINVAL;
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
	int cpu, ret;

	for_each_possible_cpu(cpu)
		raw_spin_lock_init(&per_cpu(ego_idle_cpus, cpu).lock);
	ret = register_trace_cpu_idle(ego_idle_transition, NULL);
	if (ret)
		return ret;
	ret = cpufreq_register_governor(&cpufreq_gov_energy_aware);
	if (ret) {
		unregister_trace_cpu_idle(ego_idle_transition, NULL);
		tracepoint_synchronize_unregister();
	}
	return ret;
}
fs_initcall(eagov_register);
