#!/usr/bin/env python3
"""Exercise actual PTE/PMD callbacks with lock and OFF-transition assertions.

Mocks validate callback ordering; they do not emulate ARM64 page tables or SMP.
"""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(os.environ.get("MGLRU_TEST_SOURCE", "mm/vmscan.c")).read_text()
def function(marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]

stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define PAGE_SIZE 4096UL
#define PAGE_SHIFT 12
#define PMD_MASK (~(2UL*1024*1024-1))
#define SWAP_CLUSTER_MAX 32
#define BITS_TO_LONGS(n) (((n)+63)/64)
#define max(a,b) ((a)>(b)?(a):(b))
#define for_each_set_bit(i,b,n) for ((i)=0;(i)<(n);++(i)) if ((b)[(i)/64] & (1UL<<((i)%64)))
#define __set_bit(i,b) ((b)[(i)/64] |= (1UL<<((i)%64)))
#define VM_BUG_ON_PAGE(c,p) assert(!(c))
#define lockdep_assert_held(p) do { (void)(p); assert(table_held); } while(0)
#define READ_ONCE(x) (x)
typedef int spinlock_t;
enum { MM_LEAF_HOLE, MM_LEAF_OLD, MM_LEAF_OTHER_NODE, MM_LEAF_DIRTY,
       MM_LEAF_YOUNG, MM_LEAF_OTHER_MEMCG };
struct zone { spinlock_t lru_lock; };
struct lrugen { bool enabled[2]; unsigned long max_seq; };
struct lruvec { struct lrugen evictable; struct zone zone; };
struct mm_walk_args {
    struct lruvec *lruvec; void *memcg; unsigned long start_pfn,end_pfn;
    int mm_stats[6];
};
struct page { struct zone *zone; bool lru,unevictable,dirty,matches,file; int gen,refs; };
typedef struct { bool present,young,dirty,special; unsigned long pfn; } pte_t;
typedef struct { bool unstable; } pmd_t;
struct mm_walk { void *private,*vma,*mm; };
struct vm_area_struct { unsigned long vm_start,vm_end; };
struct page_vma_mapped_walk {
    struct page *page; pte_t *pte; spinlock_t *ptl;
    struct vm_area_struct *vma; unsigned long address;
};
static struct page pages[2];
static pte_t table[2];
static spinlock_t table_lock;
static bool table_held,zone_held,turn_off,global_enabled=true;
static int promoted,clears;
static bool pte_present(pte_t p) { return p.present; }
static bool pte_young(pte_t p) { return p.young; }
static bool pte_dirty(pte_t p) { return p.dirty; }
static unsigned long pte_pfn(pte_t p) { return p.pfn; }
static bool pfn_valid(unsigned long n) { return n<2; }
static struct page *pfn_to_page(unsigned long n) __attribute__((unused));
static struct page *pfn_to_page(unsigned long n) { assert(table_held); return &pages[n]; }
static struct page *vm_normal_page(void *v,unsigned long a,pte_t p)
{ (void)v; (void)a; assert(table_held); return p.special ? NULL : &pages[p.pfn]; }
static struct page *compound_head(struct page *p) { return p; }
static struct zone *page_zone(struct page *p) { return p->zone; }
static struct zone *lruvec_zone(struct lruvec *l) { return &l->zone; }
static bool get_page_unless_zero(struct page *p) { assert(table_held); ++p->refs; return true; }
static void put_page(struct page *p) { assert(p->refs>0); --p->refs; }
static bool PageDirty(struct page *p) { return p->dirty; }
static void set_page_dirty(struct page *p) { assert(table_held); p->dirty=true; }
static bool PageLRU(struct page *p) { return p->lru; }
static bool PageUnevictable(struct page *p) { return p->unevictable; }
static int page_lru_gen(struct page *p) { return p->gen; }
static int page_is_file_cache(struct page *p) { return p->file; }
static bool lru_gen_enabled(void) { return global_enabled; }
static bool lru_gen_page_memcg_matches(struct page *p,void *m)
{ (void)m; return p->matches; }
static struct lruvec *active;
static struct lruvec *mem_cgroup_page_lruvec(struct page *p,struct zone *z)
{ (void)p; (void)z; return active; }
static bool PageTail(struct page *p) { (void)p; return false; }
static unsigned long pmd_addr_end(unsigned long a,unsigned long e) { (void)a; return e; }
static struct page *pte_page(pte_t p) { assert(table_held); return &pages[p.pfn]; }
static int lru_gen_diag_scan_calls,lru_gen_diag_scan_promoted;
static bool lru_gen_scan_around_runtime=true;
static void atomic64_inc(int *p) { ++*p; }
static void atomic64_add(int n,int *p) { *p+=n; }
static int hpage_nr_pages(struct page *p) { (void)p; return 1; }
static void arch_enter_lazy_mmu_mode(void) {}
static void arch_leave_lazy_mmu_mode(void) {}
static void zone_lock(spinlock_t *l)
{ (void)l; assert(table_held && !zone_held); zone_held=true;
  if (turn_off) active->evictable.enabled[1]=false; }
#define raw_unused(x) ((void)(x))
#define spin_lock_irqsave(l,f) do { (f)=0; zone_lock(l); } while(0)
#define spin_unlock_irqrestore(l,f) do { raw_unused(l); raw_unused(f); zone_held=false; } while(0)
#define spin_lock_irq(l) zone_lock(l)
#define spin_unlock_irq(l) do { raw_unused(l); zone_held=false; } while(0)
static int lru_gen_from_seq(unsigned long s) { return s%8; }
static bool ptep_test_and_clear_young(void *v,unsigned long a,pte_t *p)
{ (void)v; (void)a; assert(table_held); ++clears; bool old=p->young; p->young=false; return old; }
static bool lru_gen_promote_accessed_locked(struct page *p,struct lruvec *l,int g)
{ assert(table_held && zone_held && l->evictable.enabled[1]);
  assert(p->matches && p->lru); p->gen=g; ++promoted; return true; }
static bool pmd_trans_unstable(pmd_t *p) { return p->unstable; }
static pte_t *pte_offset_map_lock(void *m,pmd_t *p,unsigned long a,spinlock_t **lock)
{ (void)m; (void)p; (void)a; assert(!table_held); table_held=true; *lock=&table_lock; return table; }
static void pte_unmap_unlock(pte_t *p,spinlock_t *l)
{ assert(p==table && l==&table_lock && table_held && !zone_held); table_held=false; }
'''
main = r'''
static struct lruvec l;
static struct mm_walk_args args;
static struct mm_walk walk;
static void reset(void)
{
    memset(&l,0,sizeof(l)); memset(&args,0,sizeof(args));
    l.evictable.enabled[1]=true; l.evictable.max_seq=7; active=&l;
    args.lruvec=&l; args.end_pfn=2; walk.private=&args;
    for (int i=0;i<2;i++) {
        pages[i]=(struct page){.zone=&l.zone,.lru=true,.matches=true,.file=true,.gen=3};
        table[i]=(pte_t){.present=true,.young=true,.pfn=i};
    }
    table_held=zone_held=turn_off=false; global_enabled=true; promoted=clears=0;
}
static void run(void)
{ pmd_t p={0}; lru_gen_pmd_entry(&p,0,2*PAGE_SIZE,&walk);
  assert(!table_held && !zone_held && !pages[0].refs && !pages[1].refs); }
int main(void)
{
    reset(); run(); assert(promoted==2 && clears==2 && pages[0].gen==7);
    reset(); turn_off=true; run();
    assert(promoted==0 && clears==0 && table[0].young && table[1].young);
    reset(); global_enabled=false; run(); assert(clears==0);
    reset(); pages[0].matches=false; pages[1].lru=false; run(); assert(clears==0);
    reset(); pages[0].unevictable=true; pages[1].gen=-1; run(); assert(clears==0);
    reset(); table[0].special=true; table[1].present=false; run(); assert(clears==0);
    reset(); table[0].young=false; table[1].pfn=3; run(); assert(clears==0);
    reset(); pmd_t huge={.unstable=true};
    lru_gen_pmd_entry(&huge,0,2*PAGE_SIZE,&walk); assert(clears==0 && !table_held);
    struct vm_area_struct vma={.vm_end=2*PAGE_SIZE};
    struct page_vma_mapped_walk pvmw={.page=&pages[0],.pte=table,.ptl=&table_lock,.vma=&vma};
    reset(); table_held=true; lru_gen_scan_around(&pvmw);
    assert(clears==2 && promoted==2 && !zone_held); table_held=false;
    reset(); table[0].young=false; pages[1].lru=false;
    table_held=true; lru_gen_scan_around(&pvmw);
    assert(clears==0 && table[1].young); table_held=false;
    reset(); table[0].young=false; pages[1].file=false; /* anon reclaim disabled */
    table_held=true; lru_gen_scan_around(&pvmw);
    assert(clears==0 && table[1].young); table_held=false;
    reset(); table[0].young=false; table[1].special=true;
    table_held=true; lru_gen_scan_around(&pvmw);
    assert(clears==0 && table[1].young); table_held=false;
    puts("PASS: PTE table locked across lookup, pin and access-bit clearing");
    puts("PASS: OFF, other memcg, non-LRU and special mappings keep access bits");
    puts("PASS: rmap neighbors respect per-type eligibility and special mappings");
}
'''
pte = function("static int lru_gen_pte_entry(")
scan = function("void lru_gen_scan_around(")
if "static int lru_gen_pmd_entry(" in source:
    pmd = function("static int lru_gen_pmd_entry(")
else:
    # Model this tree's old generic ->pte_entry path, which holds no PTE lock.
    pmd = r'''static int lru_gen_pmd_entry(pmd_t *p,unsigned long a,unsigned long e,struct mm_walk *w)
    { (void)p; for (int i=0;a<e;i++,a+=PAGE_SIZE) lru_gen_pte_entry(&table[i],a,a+PAGE_SIZE,w); return 0; }'''
with tempfile.TemporaryDirectory(prefix="mglru-pte-test-") as tmp:
    c, exe = Path(tmp)/"pte.c", Path(tmp)/"pte"
    c.write_text(stub+pte+pmd+scan+main)
    subprocess.run([os.environ.get("HOSTCC","cc"),"-std=gnu99","-Wall","-Wextra",
                    "-Werror","-Wno-unused-function","-Wno-unused-parameter",
                    str(c),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=10)
walk = function("static void lru_gen_walk_mm_legacy(")
assert ".pmd_entry = lru_gen_pmd_entry" in walk and ".pte_entry" not in walk
