/*
 * Minimal MGLRU interface for the Linux 4.4 backport.
 *
 * The implementation is intentionally kept behind CONFIG_LRU_GEN so a
 * disabled build retains the stock 4.4 LRU path.
 */
#ifndef _LINUX_MGLRU_H
#define _LINUX_MGLRU_H

#include <linux/types.h>
#include <linux/mm_types.h>

#ifdef CONFIG_LRU_GEN

#define MGLRU_NR_GENS 4U
#define MGLRU_MIN_GENS 2U
#define MGLRU_DEFAULT_INTERVAL_MS 500U

struct lruvec;
struct page;

void lru_gen_init_lruvec(struct lruvec *lruvec);
void lru_gen_add_page(struct page *page, struct lruvec *lruvec, bool lru);
void lru_gen_del_page(struct page *page, struct lruvec *lruvec, bool lru);
void lru_gen_update_lruvec(struct lruvec *lruvec);
bool lru_gen_enabled(void);
bool lru_gen_page_reclaimable(struct page *page);
void lru_gen_page_reclaimed(struct page *page);

static inline void mglru_init_lruvec(struct lruvec *lruvec)
{
	lru_gen_init_lruvec(lruvec);
}

static inline void mglru_add_page(struct page *page, struct lruvec *lruvec)
{
	lru_gen_add_page(page, lruvec, true);
}

static inline void mglru_touch_page(struct page *page)
{
	(void)page;
}

static inline void mglru_update_lruvec(struct lruvec *lruvec)
{
	lru_gen_update_lruvec(lruvec);
}

static inline bool mglru_page_reclaimable(struct page *page)
{
	return lru_gen_page_reclaimable(page);
}

static inline void mglru_page_reclaimed(struct page *page)
{
	lru_gen_page_reclaimed(page);
}

static inline bool mglru_enabled(void)
{
	return lru_gen_enabled();
}

#else

struct lruvec;
struct page;

static inline void mglru_init_lruvec(struct lruvec *lruvec) { }
static inline void mglru_add_page(struct page *page, struct lruvec *lruvec) { }
static inline void mglru_touch_page(struct page *page) { }
static inline void mglru_update_lruvec(struct lruvec *lruvec) { }
static inline bool mglru_page_reclaimable(struct page *page) { return true; }
static inline void mglru_page_reclaimed(struct page *page) { }
static inline bool mglru_enabled(void) { return false; }

#endif

#endif /* _LINUX_MGLRU_H */
