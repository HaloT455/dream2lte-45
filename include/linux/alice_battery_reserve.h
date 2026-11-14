/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_ALICE_BATTERY_RESERVE_H
#define _LINUX_ALICE_BATTERY_RESERVE_H

#ifdef CONFIG_ALICE_BATTERY_RESERVE
void alice_battery_reserve_update(int actual, bool charging);
bool alice_battery_reserve_emergency(void);
#else
static inline void alice_battery_reserve_update(int actual, bool charging)
{
}
static inline bool alice_battery_reserve_emergency(void)
{
	return false;
}
#endif

#endif
