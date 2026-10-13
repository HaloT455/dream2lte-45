#!/usr/bin/env python3
"""Run the actual MGLRU batch with concurrent isolation and slow-I/O faults.

Pageout/list operations are stubs. This verifies control flow, wait bounds,
counter balance and writeback feedback, not handset stability.
"""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(os.environ.get("MGLRU_TEST_SOURCE", "mm/vmscan.c")).read_text()

def function(marker):
    start=source.index(marker); opening=source.index("{", start); depth,end=1,opening+1
    while depth:
        depth+=(source[end]=="{")-(source[end]=="}"); end+=1
    return source[start:end]

stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#define SWAP_CLUSTER_MAX 32UL
#define HZ 250
#define __GFP_IO 1
#define __GFP_FS 2
#define BLK_RW_ASYNC 0
#define TTU_UNMAP 0
#define min(a,b) ((a)<(b)?(a):(b))
enum { NR_INACTIVE_ANON, NR_INACTIVE_FILE, NR_ISOLATED_ANON, NR_ISOLATED_FILE, NR_PAGES_SCANNED };
enum { ZONE_WRITEBACK, ZONE_CONGESTED, ZONE_DIRTY };
enum { PGSCAN_KSWAPD, PGSCAN_DIRECT, PGSTEAL_KSWAPD, PGSTEAL_DIRECT };
struct zone { unsigned long flags, state[5]; int lru_lock; };
struct lruvec { struct zone zone; };
struct scan_control { unsigned int gfp_mask; bool sane,hibernation_mode;
                      unsigned long nr_scanned,nr_reclaimed; };
struct list_head { int dummy; };
struct page { int dummy; };
#define LIST_HEAD(name) struct list_head name={0}
#define list_for_each_entry(p,h,m) for ((p)=NULL; (p)!=NULL; (p)=NULL)
static bool kswapd,dying,may_throttle=true,release_on_wait;
static int waits,congested_waits,isolations;
static unsigned long dirty,unqueued,congested,writeback,immediate;
static struct zone *active_zone;
static int lru_gen_diag_reclaim_batches,lru_gen_diag_reclaim_scanned,lru_gen_diag_reclaim_reclaimed;
static bool current_is_kswapd(void) { return kswapd; }
static bool sane_reclaim(struct scan_control *s) { return s->sane; }
static unsigned long zone_page_state(struct zone *z,int n) { return z->state[n]; }
static bool fatal_signal_pending(void *p) { (void)p; return dying; }
#define current NULL
static bool current_may_throttle(void) { return may_throttle; }
static void set_bit(int n,unsigned long *p) { *p |= 1UL<<n; }
static void congestion_wait(int rw,unsigned long time)
{
    (void)rw; assert(time==HZ/10); assert(!active_zone->lru_lock);
    assert(++waits<=1); /* isolation must not loop indefinitely */
    if (release_on_wait) active_zone->state[NR_ISOLATED_ANON]=0;
}
static void wait_iff_congested(struct zone *z,int rw,unsigned long time)
{ (void)rw; assert(time==HZ/10 && !z->lru_lock); ++congested_waits; }
static struct zone *lruvec_zone(struct lruvec *l) { return &l->zone; }
static void lru_add_drain(void) {}
static unsigned long lru_gen_isolate_oldest(struct lruvec *l,struct scan_control *s,
                    int type,int tier,struct list_head *dst,unsigned long n,unsigned long *scanned)
{ (void)s; (void)tier; (void)dst; ++isolations; *scanned=n;
  l->zone.state[NR_ISOLATED_ANON+type]+=n; return n; }
static void atomic64_inc(int *p) { ++*p; }
static void atomic64_add(unsigned long n,int *p) { *p+=n; }
static bool global_reclaim(struct scan_control *s) { (void)s; return true; }
static void __mod_zone_page_state(struct zone *z,int n,long delta) { z->state[n]+=delta; }
static void __count_zone_vm_events(int e,struct zone *z,unsigned long n) { (void)e;(void)z;(void)n; }
static unsigned long shrink_page_list(struct list_head *h,struct zone *z,struct scan_control *s,
      int unmap,unsigned long *d,unsigned long *u,unsigned long *c,unsigned long *w,unsigned long *i,bool force)
{ (void)h;(void)z;(void)s;(void)unmap;(void)force;
  *d=dirty; *u=unqueued; *c=congested; *w=writeback; *i=immediate; return writeback?0:32; }
#define PageMlocked(p) false
#define page_mapped(p) false
#define PageReferenced(p) false
#define PageActive(p) false
#define SetPageActive(p) ((void)(p))
#define SetPageWorkingset(p) ((void)(p))
#define ClearPageReferenced(p) ((void)(p))
static void spin_lock_irq(int *p) { assert(!*p); *p=1; }
static void spin_unlock_irq(int *p) { assert(*p); *p=0; }
static void putback_inactive_pages(struct lruvec *l,struct list_head *h)
{ (void)h; assert(l->zone.lru_lock); }
static bool lru_gen_advance_min_locked(struct lruvec *l,int t) { (void)l;(void)t; return false; }
static void mem_cgroup_uncharge_list(struct list_head *h) { (void)h; }
static void free_hot_cold_page_list(struct list_head *h,bool cold) { (void)h;(void)cold; }
'''
main = r'''
static struct lruvec l;
static struct scan_control s;
static void reset(void)
{
    l=(struct lruvec){0}; s=(struct scan_control){.sane=true,.gfp_mask=__GFP_IO|__GFP_FS};
    l.zone.state[NR_INACTIVE_ANON]=256; l.zone.state[NR_INACTIVE_FILE]=256;
    active_zone=&l.zone; kswapd=dying=release_on_wait=false; may_throttle=true;
    waits=congested_waits=isolations=0; dirty=unqueued=congested=writeback=immediate=0;
}
static unsigned long batch(int type) { return lru_gen_reclaim_batch(&l,&s,type,0,32); }
int main(void)
{
    reset(); l.zone.state[NR_ISOLATED_ANON]=64;
    assert(batch(0)==0 && waits==1 && !isolations && !s.nr_scanned && !s.nr_reclaimed);
    assert(l.zone.state[NR_ISOLATED_ANON]==64);
    /* Saturation of anon must not prevent file progress. */
    assert(batch(1)==32 && isolations==1 && s.nr_reclaimed==32);
    assert(!l.zone.state[NR_ISOLATED_FILE]);
    reset(); l.zone.state[NR_ISOLATED_ANON]=64; release_on_wait=true;
    assert(batch(0)==32 && waits==1 && !l.zone.state[NR_ISOLATED_ANON]);
    reset(); l.zone.state[NR_ISOLATED_ANON]=64; s.gfp_mask=0; may_throttle=false;
    assert(batch(0)==32 && !waits && !congested_waits); /* NOIO's relaxed threshold */
    reset(); l.zone.state[NR_ISOLATED_ANON]=64; kswapd=true;
    assert(batch(0)==32 && !waits && !congested_waits);
    reset(); l.zone.state[NR_ISOLATED_ANON]=64; s.sane=false;
    assert(batch(0)==32 && !waits); /* legacy memcg exemption */
    reset(); kswapd=true; dirty=congested=unqueued=writeback=32; immediate=1;
    assert(!batch(0) && waits==1 && !congested_waits && !l.zone.state[NR_ISOLATED_ANON]);
    assert((l.zone.flags & 7)==7); /* feedback reaches the outer 4.4 reclaim loop */
    reset(); dirty=congested=32; batch(1);
    assert((l.zone.flags & (1UL<<ZONE_CONGESTED)) && congested_waits==1 && !waits);
    reset(); s.hibernation_mode=true; batch(1); assert(!congested_waits);
    puts("PASS: concurrent isolation waits once, rechecks, keeps counters balanced");
    puts("PASS: independent page types, kswapd, NOIO and legacy memcg retain progress");
    puts("PASS: MGLRU reports slow writeback and throttles outside LRU lock");
}
'''
parts=[function("static int too_many_isolated(")]
for marker in ["static void reclaim_writeback_throttle(", "static bool lru_gen_reclaim_throttled("]:
    if marker in source: parts.append(function(marker))
parts.append(function("static unsigned long lru_gen_reclaim_batch("))
with tempfile.TemporaryDirectory(prefix="r7-reclaim-") as tmp:
    c,exe=Path(tmp)/"reclaim.c",Path(tmp)/"reclaim"
    c.write_text(stub+"\n".join(parts)+main)
    subprocess.run([os.environ.get("HOSTCC","cc"),"-std=gnu99","-Wall","-Wextra",
                    "-Werror","-Wno-unused-function",str(c),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=10)
