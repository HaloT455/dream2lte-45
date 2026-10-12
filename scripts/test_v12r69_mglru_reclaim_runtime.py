#!/usr/bin/env python3
"""Run the actual reclaim loop with skipped-page and huge-page overshoot.

Isolation/pageout are mocked; this checks termination and the caller's budget,
not physical page lists, swap I/O or target-device performance.
"""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(os.environ.get("MGLRU_TEST_SOURCE", "mm/vmscan.c")).read_text()
start = source.index("static void lru_gen_shrink_lruvec_full(")
opening = source.index("{", start)
depth, end = 1, opening + 1
while depth:
    depth += (source[end] == "{") - (source[end] == "}")
    end += 1
function = source[start:end]

stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#define SWAP_CLUSTER_MAX 32UL
#define ANON_AND_FILE 2
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,y) ((x)=(y))
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define max_t(t,a,b) max((t)(a),(t)(b))
#define time_before(a,b) ((long)((a)-(b))<0)
#define time_after_eq(a,b) (!time_before(a,b))
#define msecs_to_jiffies(x) (x)
#define spin_lock_irq(x) ((void)(x))
#define spin_unlock_irq(x) ((void)(x))
#define cond_resched() ((void)0)
#define pr_info_ratelimited printf
enum { NR_ACTIVE_ANON, NR_INACTIVE_ANON, NR_ACTIVE_FILE,
       NR_INACTIVE_FILE, NR_FREE_PAGES };
struct zone { int lru_lock; const char *name; };
struct lrugen {
    bool enabled[2]; unsigned long reclaim_backoff_until, max_seq, min_seq[2];
    long sizes[8][2][1];
};
struct lruvec { struct lrugen evictable; struct zone zone; };
struct scan_control { unsigned long nr_scanned, nr_reclaimed, nr_to_reclaim; };
static unsigned long jiffies=1000, lru_gen_ptwalk_retry_after;
static bool kswapd=true;
static bool lru_gen_ptwalk_runtime, lru_gen_diag_runtime;
static int lru_gen_diag_ptwalk_rounds, lru_gen_diag_no_progress, lru_gen_diag_backoffs;
static void atomic64_inc(int *p) { ++*p; }
static struct zone *lruvec_zone(struct lruvec *l) { return &l->zone; }
static bool current_is_kswapd(void) { return kswapd; }
static unsigned long lru_gen_size_zone(struct lruvec *l) { (void)l; return 1000; }
static bool lru_gen_advance_min_locked(struct lruvec *l,int t)
{ (void)l; (void)t; return false; }
static bool lru_gen_needs_new_generation(struct lruvec *l) { (void)l; return false; }
static void lru_gen_age_lruvec_legacy(struct lruvec *l,struct scan_control *s,int w)
{ (void)l; (void)s; (void)w; }
static void lru_gen_inc_max_seq_legacy(struct lruvec *l) { (void)l; }
static unsigned long configured_budget;
static int calls, scenario;
static unsigned long lru_gen_reclaim_budget(struct lruvec *l,struct scan_control *s,int w)
{ (void)l; (void)s; (void)w; return configured_budget; }
static int lru_gen_pick_type(struct lruvec *l,int w,int *t)
{ (void)l; (void)w; *t=0; return 1; }
static int lru_gen_get_tier_to_isolate(struct lruvec *l,int t)
{ (void)l; (void)t; return 0; }
static void lru_gen_reclaim_batch(struct lruvec *l,struct scan_control *s,
                                 int t,int tier,unsigned long n)
{
    (void)l; (void)t; (void)tier;
    assert(++calls <= 8); /* Fail quickly if unsigned wrap defeats the bound. */
    switch (scenario) {
    case 0: s->nr_scanned+=n*4; break; /* protected or skipped base pages */
    case 1: s->nr_scanned+=512; ++s->nr_reclaimed; break; /* one huge page */
    case 2: s->nr_scanned+=n; s->nr_reclaimed+=n; break;
    case 3: break; /* both lists reject a batch without scanning */
    }
}
static int zone_idx(struct zone *z) { (void)z; return 0; }
static int lru_gen_from_seq(unsigned long s) { return s%8; }
static int get_nr_gens(struct lruvec *l,int t) { (void)l; (void)t; return 4; }
static unsigned long zone_page_state(struct zone *z,int n) { (void)z; (void)n; return 0; }
static void alice_sysintel_no_progress(bool b) { (void)b; }
static void alice_sysintel_reclaim(unsigned long a,unsigned long b) { (void)a; (void)b; }
'''
main = r'''
static void run(int mode,unsigned long budget,unsigned long target,int expected)
{
    struct lruvec l={.evictable={.enabled={true,true}},.zone={.name="test"}};
    /* Existing counts represent previous zone work, not this call's target. */
    struct scan_control s={.nr_scanned=700,.nr_reclaimed=300,.nr_to_reclaim=target};
    unsigned long pages;
    scenario=mode; configured_budget=budget; calls=0;
    lru_gen_shrink_lruvec_full(&l,60,&s,&pages);
    assert(calls==expected);
    if (mode==2) assert(s.nr_reclaimed==300+target);
}
int main(void)
{
    run(0,32,1000,2);
    run(0,128,1000,2);
    run(1,32,8,1);
    run(1,128,8,1);
    run(2,128,64,2);
    run(3,128,1000,2);
    struct lruvec l={.evictable={.enabled={true,true},.reclaim_backoff_until=1050},
                     .zone={.name="test"}};
    struct scan_control s={.nr_to_reclaim=32};
    unsigned long pages;
    scenario=2; configured_budget=32; calls=0;
    lru_gen_shrink_lruvec_full(&l,60,&s,&pages);
    assert(calls==0 && pages==0); /* Background cooldown remains effective. */
    kswapd=false;
    lru_gen_shrink_lruvec_full(&l,60,&s,&pages);
    assert(calls==1 && s.nr_reclaimed==32); /* Allocator may reclaim now. */
    puts("PASS: reclaim terminates on skipped-page/huge-page budget overshoot");
    puts("PASS: fallback, local reclaim target and no-scan exit preserved");
    puts("PASS: kswapd cooldown does not block direct reclaim");
}
'''
with tempfile.TemporaryDirectory(prefix="mglru-reclaim-test-") as tmp:
    c, exe = Path(tmp)/"reclaim.c", Path(tmp)/"reclaim"
    c.write_text(stub+function+main)
    subprocess.run([os.environ.get("HOSTCC","cc"),"-std=gnu99","-Wall","-Wextra",
                    "-Werror",str(c),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=10)
