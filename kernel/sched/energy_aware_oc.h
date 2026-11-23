/* SPDX-License-Identifier: GPL-2.0 */
/*
 * OC frequency states are real Exynos CAL/ASV OPPs, but the Exynos8895
 * sched-energy-costs table does not characterize their busy power.
 *
 * Estimate ONLY the uncharacterized busy-power terms relative to the
 * last native DTS state, using P_dynamic proportional to f * V^2.
 * These are engineering estimates (not Samsung power measurements).
 * Never substitute estimated values into Samsung's original DTS table.
 */
#ifndef _ENERGY_AWARE_OC_H
#define _ENERGY_AWARE_OC_H

static inline unsigned int eagov_estimate_oc_power(unsigned int base_power,
						   unsigned int base_khz,
						   unsigned int base_uv,
						   unsigned int new_khz,
						   unsigned int new_uv)
{
	unsigned int base_mv, new_mv;
	unsigned long long num, den, est;

	if (!base_power || !base_khz || !new_khz ||
	    base_uv < 300000 || new_uv < 300000 ||
	    base_uv > 3000000 || new_uv > 3000000)
		return 0;

	/* mV scaling prevents 64-bit overflow at real A53/M2 OPPs. */
	base_mv = base_uv / 1000;
	new_mv = new_uv / 1000;
	num = (unsigned long long)base_power * new_khz * new_mv * new_mv;
	den = (unsigned long long)base_khz * base_mv * base_mv;
	if (!den)
		return 0;

	est = div64_u64(num + den - 1, den);
	if (!est || est > (~0U))
		return 0;
	return (unsigned int)est;
}

static inline unsigned int eagov_estimate_oc_capacity(unsigned int base_cap,
						       unsigned int base_khz,
						       unsigned int new_khz)
{
	unsigned long long result;

	if (!base_cap || !base_khz || new_khz < base_khz)
		return 0;
	result = div64_u64((unsigned long long)base_cap * new_khz,
			   base_khz);
	/* The kernel's normalized scheduler capacity cannot exceed 1024. */
	return result > 1024U ? 1024U : (unsigned int)result;
}

#endif /* _ENERGY_AWARE_OC_H */
