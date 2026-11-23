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
	/* Samsung EGO get_next_freq(): utilization floor before energy scan. */
	unsigned int org_freq;
};

struct eagov_energy_choice {
	unsigned int state;
	unsigned long long energy;
};

/*
 * Use the Samsung energy_table.c per-CPU energy primitives in the ACTIVE
 * energy_aware path, instead of only archiving the original A53 source.
 * They operate on Exynos8895 DTS/ASV OPPs, not Exynos1280 coefficients.
 */
#include "energy_aware_samsung_et.h"

/*
 * Samsung A53 ego.c: ego_compute_energy(). Its energy input is
 * et_compute_cpu_energy() plus CLKOFF/PWROFF idle prediction. On 8895 the
 * per-core busy/idle accounting is supplied by et_compute_cpu_energy_8895.
 * Samsung Exynos8895 also has shared-cluster idle/busy costs; count ONCE.
 */
static inline unsigned long long ego_compute_energy(
		const struct eagov_energy_model *model, unsigned int index,
		const struct ego_workload *work)
{
	const struct eagov_energy_state *state = &model->states[index];
	unsigned int capacity = state->capacity;
	unsigned int peak = work->peak;
	unsigned long long energy;

	if (!capacity)
		return 0;

	/* From Samsung et_compute_cpu_energy(): normalized CPU work cost. */
	energy = et_compute_cpu_energy_8895(model, index, work);
	if (peak > capacity)
		peak = capacity;
	energy += (unsigned long long)state->cluster_power * peak;
	energy += (unsigned long long)model->cluster_idle * (capacity - peak);
	return energy * EAGOV_ENERGY_SCALE / capacity;
}

/*
 * Direct port of Samsung A53 ego_map_util_freq() from ego.c.
 * Samsung's original function: ((freq * (100 + pelt_margin))/100)*util/cap.
 *
 * 64-bit intermediates prevent overflow at ALice 2.002/2.704 GHz OPPs.
 * This is a MINIMUM OPP workload floor, NOT the final chosen frequency;
 * ego_find_energy_freq() still evaluates every eligible OPP's energy.
 */
static inline unsigned int ego_map_util_freq_8895(unsigned int util,
						    unsigned int max_freq,
						    unsigned int max_cap,
						    unsigned int pelt_margin)
{
	unsigned long long floor;

	if (!max_cap)
		return 0;
	if (pelt_margin > 100U)
		pelt_margin = 100U;
	floor = (unsigned long long)max_freq * (100U + pelt_margin) / 100U;
	floor = floor * util / max_cap;
	return floor > ~0U ? ~0U : (unsigned int)floor;
}

/*
 * Port of A53 ego_find_energy_freq(): walk OPPs at/above the work floor,
 * call ego_compute_energy() for each, and retain the lowest-energy OPP.
 * Samsung EGO's utilization-derived org_freq floor is combined with the
 * native Exynos8895 capacity floor. Scan every allowed real frequency above
 * both floors and choose the one with minimum predicted energy, as in A53.
 * Energy search always runs; donor eng-boost interpolation is omitted since
 * it could create a frequency without a corresponding CAL/ASV power state.
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
		/* Samsung ego_find_energy_freq(): skip OPPs below org_freq. */
		if (state->frequency < work->org_freq)
			continue;
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
