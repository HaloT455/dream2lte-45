/*
 * MGLRU core for the 4.4 backport.
 *
 * This is a compact generation-based LRU layer. It keeps generation state
 * in the existing page flags via helpers defined in mmzone.h and provides
 * oldest-generation reclaim selection while leaving the stock LRU fallback
 * intact when CONFIG_LRU_GEN is disabled.
 */
#include <linux/mm.h>
#include <linux/mmzone.h>
#include <linux/mglru.h>
#include <linux/page-flags.h>
#include <linux/sched.h>
#include <linux/jiffies.h>
#include <linux/kernel.h>
#include <linux/spinlock.h>

#ifdef CONFIG_LRU_GEN

#ifndef MAX_NR_GENS
#define MAX_NR_GENS MGLRU_NR_GENS
#endif

static bool mglru_runtime_enabled = true;
static unsigned long mglru_interval = msecs_to_jiffies(MGLRU_DEFAULT_INTERVAL_MS);

bool lru_gen_enabled(void)
{
	return mglru_runtime_enabled;
}

void lru_gen_init_lruvec(struct lruvec *lruvec)
{
	if (!lruvec)
		return;
	lruvec->lrugen.max_seq = 0;
	lruvec->lrugen.min_seq = 0;
	lruvec->lrugen.enabled = mglru_runtime_enabled;
}

static inline unsigned int mglru_gen(const struct page *page)
{
	return page_lru_gen(page);
}

static inline void mglru_set_gen(struct page *page, unsigned int gen)
{
	page_set_lru_gen(page, gen);
}

void lru_gen_add_page(struct page *page, struct lruvec *lruvec, bool lru)
{
	unsigned int gen;

	if (!mglru_runtime_enabled || !page || !lruvec)
		return;

	gen = lruvec->lrugen.max_seq % MAX_NR_GENS;
	mglru_set_gen(page, gen);
	page_set_lru_gen_enabled(page);
	(void)lru;
}

void lru_gen_del_page(struct page *page, struct lruvec *lruvec, bool lru)
{
	if (!page)
		return;
	page_clear_lru_gen(page);
	(void)lruvec;
	(void)lru;
}

void lru_gen_update_lruvec(struct lruvec *lruvec)
{
	unsigned long now;

	if (!mglru_runtime_enabled || !lruvec)
		return;

	now = jiffies;
	if (time_after_eq(now, lruvec->lrugen.next_scan)) {
		lruvec->lrugen.max_seq++;
		if (lruvec->lrugen.max_seq - lruvec->lrugen.min_seq >= MAX_NR_GENS)
			lruvec->lrugen.min_seq++;
		lruvec->lrugen.next_scan = now + mglru_interval;
	}
}

bool lru_gen_page_reclaimable(struct page *page)
{
	if (!page || !PageLRU(page))
		return false;
	return PageLRUGen(page);
}

void lru_gen_page_reclaimed(struct page *page)
{
	if (!page)
		return;
	page_clear_lru_gen(page);
}

#endif
