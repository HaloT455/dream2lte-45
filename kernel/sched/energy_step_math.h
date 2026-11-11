/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _SCHED_ENERGY_STEP_MATH_H
#define _SCHED_ENERGY_STEP_MATH_H

/*
 * Include after struct capacity_state is declared. Keep this calculation free
 * of scheduler/driver side effects: EAS and the governor must predict the
 * same requested capacity. Capacities are normalized to at most 1024.
 *
 * Adapted from Samsung's find_step_power()/find_allowed_capacity() in the
 * Exynos850 4.19 EMS governor. Unlike PART, this backport estimates active
 * time from frequency-invariant utilization / current capacity. The DT power
 * scale is relative; this does not turn it into a calibrated watt reading.
 */
static inline unsigned long
energy_step_target_capacity(const struct capacity_state *states,
		unsigned int count, unsigned long util,
		unsigned long current_cap, unsigned long floor,
		unsigned long ceiling, unsigned int steps)
{
	unsigned long target, budget, power, allowed, busy_base;
	unsigned long light_load, heavy_load;
	unsigned int i;

	if (floor > ceiling)
		floor = ceiling;
	if (util > ceiling)
		util = ceiling;
	if (!util)
		return floor;

	/* With spare capacity, request only the capacity needed by the load. */
	light_load = ceiling >> 2;
	heavy_load = ceiling - light_load;
	if (util <= light_load)
		return util > floor ? util : floor;

	/* Keep the existing headroom and power step available at heavy load. */
	target = util + (util >> 2);
	if (states && count && steps) {
		for (i = 0; i + 1 < count; i++)
			if (states[i].cap >= current_cap)
				break;
		power = states[i].power;
		budget = (states[count - 1].power - states[0].power) / steps;
		if (budget > states[count - 1].power - power)
			power = states[count - 1].power;
		else
			power += budget;
		for (i = 0; i + 1 < count; i++)
			if (states[i].power >= power)
				break;
		allowed = states[i].cap;
		busy_base = current_cap > util ? current_cap : util;
		allowed = (unsigned long)((unsigned long long)allowed * util /
					  busy_base);
		if (allowed > target)
			target = allowed;
	}
	if (target > ceiling)
		target = ceiling;
	/* Blend the boost between 25% and 75% of the current policy limit. */
	if (util < heavy_load)
		target = util + (unsigned long long)(target - util) *
			 (util - light_load) / (heavy_load - light_load);
	if (target < floor)
		target = floor;
	return target;
}

#endif
