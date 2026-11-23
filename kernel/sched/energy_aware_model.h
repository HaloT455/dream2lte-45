/*
 * EGO energy-frequency search backported from Samsung Galaxy A53.
 * Copyright (C) 2021, Samsung Electronic Corporation
 *
 * Adapted from ego_compute_energy()/ego_find_energy_freq() in:
 * s5e8825/android_kernel_samsung_s5e8825, commit
 * 2ec382e83341d79b552e77e27505228c731e6459, kernel/sched/ems/ego.c.
 *
 * GNU General Public License version 2. Exynos8895 uses its own DT energy
 * states and idle powers; Exynos1280 power coefficients are not transferable.
 */
#ifndef _ENERGY_AWARE_MODEL_H
#define _ENERGY_AWARE_MODEL_H

#define EAGOV_NO_STATE (~0U)
#define EAGOV_ENERGY_SCALE 1024U

struct eagov_energy_state {
	unsigned int frequency;
	unsigned int capacity;
	unsigned int core_power;
	unsigned int cluster_power;
};

struct eagov_energy_model {
	struct eagov_energy_state *states;
	unsigned int nr_states;
	unsigned int core_idle;
	unsigned int core_pwroff;
	unsigned int cluster_idle;
};

struct ego_cpu_work {
	unsigned int util;
	unsigned int clkoff_ratio;
};

struct ego_workload {
	struct ego_cpu_work *cpus;
	unsigned int nr_cpus;
	unsigned int peak;
};

struct eagov_energy_choice {
	unsigned int state;
	unsigned long long energy;
};

/*
 * A53 EGO: normalize per-CPU active time and distribute residual idle time
 * between CLKOFF and PWROFF using that CPU's observed idle history. Sum
 * active energy (et_compute_cpu_energy on A53) and residual idle energy.
 * S8+ adds its explicit shared-cluster busy/idle cost once per policy.
 */
static inline unsigned long long ego_compute_energy(
		const struct eagov_energy_model *model, unsigned int index,
		const struct ego_workload *work)
{
	const struct eagov_energy_state *state = &model->states[index];
	unsigned int capacity = state->capacity;
	unsigned int cpu, peak = work->peak;
	unsigned long long energy = 0;

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
	if (peak > capacity)
		peak = capacity;
	energy += (unsigned long long)state->cluster_power * peak;
	energy += (unsigned long long)model->cluster_idle * (capacity - peak);
	return energy * EAGOV_ENERGY_SCALE / capacity;
}

/*
 * Port of A53 ego_find_energy_freq(): walk OPPs at/above the work floor,
 * call ego_compute_energy() for each, and retain the lowest-energy OPP.
 * The work floor is resolved in DT capacity units instead of a linear kHz
 * estimate. Energy search always runs; the A53 busy-only gate and optional
 * eng-boost interpolation are removed for this energy-aware-only profile.
 */
static inline struct eagov_energy_choice ego_find_energy_freq(
		const struct eagov_energy_model *model,
		const struct ego_workload *work, unsigned int min_freq,
		unsigned int max_freq)
{
	struct eagov_energy_choice best = { EAGOV_NO_STATE, ~0ULL };
	unsigned int required, ceiling = EAGOV_NO_STATE, i;

	if (!model->nr_states || !work->nr_cpus)
		return best;

	/* Capacity headroom constrains work, never computes a clock target. */
	required = (work->peak * 9U + 7U) / 8U;
	for (i = 0; i < model->nr_states; i++) {
		const struct eagov_energy_state *state = &model->states[i];
		unsigned long long energy;

		if (state->frequency < min_freq || state->frequency > max_freq)
			continue;
		ceiling = i;
		if (state->capacity < required)
			continue;

		energy = ego_compute_energy(model, i, work);
		if (best.state == EAGOV_NO_STATE || energy < best.energy) {
			best.state = i;
			best.energy = energy;
		}
	}

	/* Saturation/thermal caps: highest permitted modeled state. */
	if (best.state == EAGOV_NO_STATE && ceiling != EAGOV_NO_STATE) {
		best.state = ceiling;
		best.energy = ego_compute_energy(model, ceiling, work);
	}
	return best;
}

#endif
