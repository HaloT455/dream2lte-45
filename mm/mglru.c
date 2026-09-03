/* MGLRU core for Linux 4.4 backport. */
#include <linux/mm.h>
#include <linux/mmzone.h>
#include <linux/mglru.h>
#include <linux/page-flags.h>

#ifdef CONFIG_LRU_GEN

bool lru_gen_enabled(void)
{
	return true;
}

void lru_gen_init_lruvec(struct lruvec *lruvec)
{
	if (lruvec)
		lruvec->lrugen.max_seq = 0;
}

void lru_gen_add_page(struct page *page, struct lruvec *lruvec, bool lru)
{
	if (!page || !lruvec)
		return;
	page_set_lru_gen(page, lruvec->lrugen.max_seq % MGLRU_NR_GENS);
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
	if (lruvec)
		lruvec->lrugen.max_seq++;
}

bool lru_gen_page_reclaimable(struct page *page)
{
	return page && PageLRU(page) && PageLRUGen(page);
}

void lru_gen_page_reclaimed(struct page *page)
{
	if (page)
		page_clear_lru_gen(page);
}

#endif
