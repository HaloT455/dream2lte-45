#!/usr/bin/env python3
"""Static regressions for V12R5O generation-list accounting reconciliation.

This is source invariant checking, NOT a proof of stability on the phone.
"""
from pathlib import Path

source = Path("mm/vmscan.c").read_text()
fn = source[source.index("static bool lru_gen_reconcile_misplaced_locked("):
            source.index("static void lru_gen_promote_page_locked(", source.index(
                "static bool lru_gen_reconcile_misplaced_locked("))]
assert "lockdep_assert_held(&lruvec_zone(lruvec)->lru_lock)" in fn
assert "lrugen->sizes[source_gen][type][zid] < pages" in fn
assert fn.index("lrugen->sizes[source_gen][type][zid] < pages") < fn.index(
    "lru_gen_update_size(page, lruvec, source_gen, target_gen)")
assert "atomic64_inc(&lru_gen_diag_misplaced_fixed)" in fn
assert "atomic64_inc(&lru_gen_diag_misplaced_rejected)" in fn
assert "pr_warn_ratelimited" in fn

promote = source[source.index("static void lru_gen_promote_page_locked("):
                 source.index("static bool lru_gen_should_skip_page(")]
assert "lru_gen_reconcile_misplaced_locked(page, lruvec," in promote
assert "goto sort;" in promote

isolate = source[source.index("static unsigned long lru_gen_isolate_oldest("):
                 source.index("static unsigned long lru_gen_reclaim_batch(")]
assert "lru_gen_reconcile_misplaced_locked(page, lruvec," in isolate
assert "list_move_tail(&page->lru, head);" in isolate

stats = source[source.index("static ssize_t lru_gen_stats_show("):
               source.index("static struct kobj_attribute lru_gen_stats_attr")]
for key in ("misplaced_fixed=%lld", "misplaced_rejected=%lld",
            "atomic64_set(&lru_gen_diag_misplaced_fixed, 0)",
            "atomic64_set(&lru_gen_diag_misplaced_rejected, 0)"):
    assert key in stats, key

def guarded_transfer(source_pages, target_pages, pages):
    if source_pages < pages:
        return source_pages, target_pages, False
    return source_pages - pages, target_pages + pages, True

assert guarded_transfer(32, 0, 32) == (0, 32, True)
assert guarded_transfer(16, 2, 32) == (16, 2, False)
assert guarded_transfer(0, 0, 1) == (0, 0, False)
print("PASS: V12R5O source invariants and guarded accounting model")
print("NOTE: These checks cannot validate runtime list membership or fix ghost counts.")
