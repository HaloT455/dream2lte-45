/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Copyright (C) 2019-2023 Sultan Alsawaf <sultan@kerneltoast.com>.
 */
#ifndef _SIMPLE_LMK_H_
#define _SIMPLE_LMK_H_

struct mm_struct;

#ifdef CONFIG_ANDROID_SIMPLE_LMK
void simple_lmk_decide_reclaim(int kswapd_priority);
bool simple_lmk_oom_reclaim(void);
void simple_lmk_mm_freed(struct mm_struct *mm);
#else
static inline void simple_lmk_decide_reclaim(int kswapd_priority)
{
}

static inline bool simple_lmk_oom_reclaim(void)
{
	return false;
}

static inline void simple_lmk_mm_freed(struct mm_struct *mm)
{
}
#endif

#endif /* _SIMPLE_LMK_H_ */
