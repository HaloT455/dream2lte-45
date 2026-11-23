/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Samsung Galaxy A53 EGO energy_table.c -> Exynos8895 Linux 4.4 adapter.
 *
 * Direct algorithmic backport of get_freq_index()/et_freq_to_cap() and
 * __compute_cpu_energy()/et_compute_cpu_energy() from:
 * https://github.com/s5e8825/android_kernel_samsung_s5e8825
 * commit 2ec382e83341d79b552e77e27505228c731e6459
 * kernel/sched/ems/energy_table.c
 *
 * Copyright (C) 2018 Samsung Electronics Co., Ltd
 * Copyright (C) 2021 Samsung Electronic Corporation
 * GNU General Public License version 2.
 *
 * S8+ uses its own real DTS core/cluster busy and idle costs.  We cannot
 * copy A53 static-power temperature coefficients, DSU tables, EMS task
 * weights or Exynos1280 voltages.  Those do not exist in the 4.4 tree.
 *
 * The native DTS costs have no separate Samsung dynamic/static coefficient:
 * per-CPU busy and idle energy are normalized exactly once by capacity.
 */
#ifndef _ENERGY_AWARE_SAMSUNG_ET_H
#define _ENERGY_AWARE_SAMSUNG_ET_H

/* Samsung energy_table.c: get_freq_index() / et_freq_to_cap(). */
static inline unsigned int et_freq_to_cap_8895(
			const struct eagov_energy_model *model,
			unsigned int freq)
{
	unsigned int i;

	if (!model || !model->states || !model->nr_states)
		return 0;
	for (i = 0; i < model->nr_states; i++)
		if (model->states[i].frequency >= freq)
			return model->states[i].capacity;
	/* Never claim an uncharacterized frequency has known capacity. */
	return 0;
}

/* Samsung et_fill_energy_state(): look up the capacity state for each OPP. */
static inline unsigned int et_cap_to_state_8895(
			const struct eagov_energy_model *model,
			unsigned int cap)
{
	unsigned int i;

	if (!model || !model->states)
		return EAGOV_NO_STATE;
	for (i = 0; i < model->nr_states; i++)
		if (model->states[i].capacity >= cap)
			return i;
	return EAGOV_NO_STATE;
}

/*
 * Samsung __compute_cpu_energy() -> sum per-CPU busy + shallow/deep idle.
 * A53 used et_compute_cpu_energy() for active and a separately normalized
 * CLKOFF static term. Exynos8895 DTS explicitly carries three core idle
 * states, so preserve its native cost terms for both CLKOFF and PWROFF.
 *
 * Returns unnormalized numerator; caller divides by candidate capacity.
 */
static inline unsigned long long et_compute_cpu_energy_8895(
			const struct eagov_energy_model *model,
			unsigned int index,
			const struct ego_workload *work)
{
	const struct eagov_energy_state *state = &model->states[index];
	unsigned int capacity = state->capacity, cpu;
	unsigned long long energy = 0;

	if (!capacity)
		return 0;

	for (cpu = 0; cpu < work->nr_cpus; cpu++) {
		unsigned int util = work->cpus[cpu].util;
		unsigned int ratio = work->cpus[cpu].clkoff_ratio;
		unsigned int idle_util, clkoff;

		if (util > capacity)
			util = capacity;
		if (ratio > EAGOV_ENERGY_SCALE)
			ratio = EAGOV_ENERGY_SCALE;
		idle_util = capacity - util;
		clkoff = idle_util * ratio / EAGOV_ENERGY_SCALE;

		energy += (unsigned long long)state->core_power * util;
		energy += (unsigned long long)model->core_idle * clkoff;
		energy += (unsigned long long)model->core_pwroff *
			  (idle_util - clkoff);
	}
	return energy;
}

#endif /* _ENERGY_AWARE_SAMSUNG_ET_H */
