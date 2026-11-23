/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Copyright (C) 2021, Samsung Electronic Corporation
 * Samsung A53 EGO idle-history backport: eight 4 ms CLKOFF/PWROFF periods.
 * Replaces the 5.10 MLT interfaces with 4.4 cpu_idle residency events.
 */
#ifndef _ENERGY_AWARE_IDLE_H
#define _ENERGY_AWARE_IDLE_H

#define EGO_IDLE_PERIOD_NS 4000000ULL
#define EGO_IDLE_PERIOD_COUNT 8U
#define EGO_IDLE_RUNNING (-1)
#define EGO_IDLE_CLKOFF 0
#define EGO_IDLE_PWROFF 1

struct ego_idle_history {
	unsigned long long clkoff[EGO_IDLE_PERIOD_COUNT];
	unsigned long long pwroff[EGO_IDLE_PERIOD_COUNT];
	unsigned long long clkoff_sum;
	unsigned long long pwroff_sum;
	unsigned long long period_start;
	unsigned long long last_update;
	unsigned int index;
	int state;
	int initialized;
};

static inline void ego_idle_update(struct ego_idle_history *idle,
		unsigned long long now, int next_state)
{
	unsigned int i;

	if (!idle->initialized) {
		idle->period_start = now - now % EGO_IDLE_PERIOD_NS;
		idle->last_update = now;
		idle->state = next_state;
		idle->initialized = 1;
		return;
	}
	if (now < idle->last_update)
		return;

	/* No events for a full history: only the current state can remain. */
	if (now - idle->last_update >=
	    EGO_IDLE_PERIOD_NS * EGO_IDLE_PERIOD_COUNT) {
		for (i = 0; i < EGO_IDLE_PERIOD_COUNT; i++) {
			idle->clkoff[i] = 0;
			idle->pwroff[i] = 0;
		}
		idle->clkoff_sum = idle->pwroff_sum = 0;
		idle->index = 0;
		idle->period_start = now - now % EGO_IDLE_PERIOD_NS -
			(EGO_IDLE_PERIOD_COUNT - 1) * EGO_IDLE_PERIOD_NS;
		idle->last_update = idle->period_start;
	}

	while (idle->last_update < now) {
		unsigned long long end =
			idle->period_start + EGO_IDLE_PERIOD_NS;
		unsigned long long delta;

		if (end > now)
			end = now;
		delta = end - idle->last_update;
		if (idle->state == EGO_IDLE_CLKOFF) {
			idle->clkoff[idle->index] += delta;
			idle->clkoff_sum += delta;
		} else if (idle->state == EGO_IDLE_PWROFF) {
			idle->pwroff[idle->index] += delta;
			idle->pwroff_sum += delta;
		}
		idle->last_update = end;
		if (end == idle->period_start + EGO_IDLE_PERIOD_NS) {
			idle->index = (idle->index + 1) % EGO_IDLE_PERIOD_COUNT;
			idle->clkoff_sum -= idle->clkoff[idle->index];
			idle->pwroff_sum -= idle->pwroff[idle->index];
			idle->clkoff[idle->index] = 0;
			idle->pwroff[idle->index] = 0;
			idle->period_start = end;
		}
	}
	idle->state = next_state;
}

static inline unsigned int ego_idle_clkoff_ratio(
		const struct ego_idle_history *idle)
{
	unsigned long long total = idle->clkoff_sum + idle->pwroff_sum;

	/* Unknown idle residency: charge shallow-idle cost conservatively. */
	return total ? idle->clkoff_sum * 1024U / total : 1024U;
}

#endif
