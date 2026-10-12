/* SPDX-License-Identifier: GPL-2.0
 *
 * ALICE System Intelligence: optional low-cost MGLRU diagnostics hooks.
 * Never delegates page table walks / page reclaim outside CPU kernel context.
 */
#ifndef _LINUX_ALICE_SYSINTEL_H
#define _LINUX_ALICE_SYSINTEL_H

#include <linux/types.h>

#ifdef CONFIG_ALICE_SYSINTEL
void alice_sysintel_reclaim(unsigned long scanned, unsigned long reclaimed);
void alice_sysintel_no_progress(bool backoff);
#else
static inline void alice_sysintel_reclaim(unsigned long scanned,
					  unsigned long reclaimed) {}
static inline void alice_sysintel_no_progress(bool backoff) {}
#endif
#endif
