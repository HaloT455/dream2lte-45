#!/usr/bin/env python3
"""Static regression guard for V12R5N MGLRU switch/reclaim changes.

Compiling is necessary but insufficient; these checks are NOT runtime safety
proofs for this experimental Samsung 4.4 backport.
"""
from pathlib import Path

v = Path("mm/vmscan.c").read_text()
h = Path("include/linux/mm_inline.h").read_text()

f_start = v.index("void lru_gen_set_state(bool enable, bool main, bool swap)")
f_end = v.index("static int __meminit", f_start)
fn = v[f_start:f_end]
switch = fn.index("static_branch_disable(&lru_gen_static_key)")
conversion = fn.index("lru_gen_change_state(memcg,")
assert conversion < switch, "Must migrate all lruvec lists before classic reclaim switch"
assert "main ? enable : lru_gen_enabled()" in fn
assert "enable && lru_gen_nr_swapfiles" in v
assert "WRITE_ONCE(lrugen->enabled[1], enable)" in v
assert "new_flags = old_flags & ~LRU_GEN_MASK" in h
assert "new_flags &= ~LRU_USAGE_MASK" in h
assert "lruvec->evictable.enabled[page_is_file_cache(page)]" in h
assert "msecs_to_jiffies(100)" in v
assert "atomic64_inc(&lru_gen_diag_empty_oldest)" in v
assert "spin_lock_irqsave(&zone->lru_lock, flags)" in v
assert "lru_gen_reclaim_batch(lruvec, sc, type" in v
print("PASS: list conversion precedes global shrinker switch")
print("PASS: per-lruvec target selection handles main and swap-only transition")
print("PASS: generation metadata cleared when leaving MGLRU")
print("PASS: empty-oldest diagnostic gated by bounded cooldown")
print("PASS: generation-aware reclaim remains in source")
print("NOTE: Kernel build, target boot, reclaim and reboot tests are not proven.")
