/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_ENERGY_STEP_H
#define _LINUX_ENERGY_STEP_H

#ifdef CONFIG_CPU_FREQ_GOV_ENERGYSTEP
unsigned long energy_step_cpu_capacity(int cpu, unsigned long util);
#else
static inline unsigned long
energy_step_cpu_capacity(int cpu, unsigned long util)
{
	return util;
}
#endif

#endif
