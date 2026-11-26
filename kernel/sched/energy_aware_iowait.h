/* SPDX-License-Identifier: GPL-2.0 */
/* Event-driven I/O-wakeup headroom; no timer or work while the CPU is idle. */
#ifndef _ENERGY_AWARE_IOWAIT_H
#define _ENERGY_AWARE_IOWAIT_H

struct eagov_iowait {
	unsigned long long last_update;
	unsigned int boost;
	bool pending;
	bool initialized;
};

static inline void eagov_iowait_update(struct eagov_iowait *io,
		unsigned long long now, bool wakeup, unsigned int capacity,
		unsigned long long tick_ns)
{
	unsigned int floor = capacity / 8U;

	if (!floor)
		floor = 1;
	if (io->initialized && (now < io->last_update ||
	    now - io->last_update > tick_ns)) {
		io->boost = 0;
		io->pending = false;
	}
	io->initialized = true;
	io->last_update = now;
	if (!wakeup || io->pending)
		return;
	io->pending = true;
	io->boost = io->boost ? io->boost * 2U : floor;
	if (io->boost > capacity)
		io->boost = capacity;
}

static inline unsigned int eagov_iowait_apply(struct eagov_iowait *io,
		unsigned int util, unsigned int capacity)
{
	unsigned int floor = capacity / 8U;

	if (!floor)
		floor = 1;
	if (io->pending)
		io->pending = false;
	else {
		io->boost >>= 1;
		if (io->boost < floor)
			io->boost = 0;
	}
	/* I/O alone may reach native capacity; it cannot request extra OC work. */
	if (io->boost > capacity)
		io->boost = capacity;
	return util > io->boost ? util : io->boost;
}

#endif
