#!/usr/bin/env python3
"""V12R5V: static safety gates for the 4.4 per-zone MGLRU reclaim bridge.

These structural checks are necessary but not sufficient for handset
stability. They do not replace arm64 compilation and physical boot testing.
"""
from pathlib import Path

v = Path("mm/vmscan.c").read_text()
cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()

def section(begin, end):
    return v[v.index(begin):v.index(end, v.index(begin))]

def ordered(fragment, *needles):
    positions = [fragment.index(needle) for needle in needles]
    assert positions == sorted(positions), (needles, positions)

# Do not race the runtime OFF transition when selecting generation/list.
isolator = section("static unsigned long lru_gen_isolate_oldest(", "static unsigned long lru_gen_reclaim_batch(")
ordered(isolator,
        "spin_lock_irq(&zone->lru_lock);",
        "if (!lru_gen_enabled() || !lrugen->enabled[type] ||",
        "gen = lru_gen_from_seq(lrugen->min_seq[type]);",
        "head = &lrugen->lists[gen][type][zid];",
        "while (!list_empty(head)",
        "unlock:\n\tspin_unlock_irq(&zone->lru_lock);")
assert "goto unlock;" in isolator
assert "goto out;" not in isolator

oldest = section("static unsigned long lru_gen_oldest_pages(", "static unsigned long lru_gen_reclaim_budget(")
ordered(oldest,
        "spin_lock_irqsave(&zone->lru_lock, flags);",
        "if (!lru_gen_enabled() || !lrugen->enabled[type] ||",
        "gen = lru_gen_from_seq(lrugen->min_seq[type]);",
        "empty = list_empty(&lrugen->lists[gen][type][zid]);",
        "spin_unlock_irqrestore(&zone->lru_lock, flags);\n\n\tif (unlikely(report))")
assert "return empty ? 0 : nr;" in oldest

advance = section("static bool lru_gen_inc_max_seq_legacy(struct lruvec *lruvec)\n{",
                  "static bool lru_gen_reconcile_misplaced_locked(")
ordered(advance,
        "spin_lock_irq(&lru_zone->lru_lock);",
        "if (!lru_gen_enabled() || !lrugen->enabled[1]) {",
        "max_seq = lrugen->max_seq;",
        "WRITE_ONCE(lrugen->max_seq, max_seq + 1);")
assert "spin_unlock_irq(&lru_zone->lru_lock);\n\t\treturn false;" in advance

floor = section("static bool lru_gen_needs_new_generation(", "static void lru_gen_shrink_lruvec_full(")
ordered(floor,
        "spin_lock_irqsave(&zone->lru_lock, flags);",
        "if (!lru_gen_enabled())",
        "get_nr_gens(lruvec, type) <= MIN_NR_GENS + 1",
        "spin_unlock_irqrestore(&zone->lru_lock, flags);")

reclaim = section("static void lru_gen_shrink_lruvec_full(", "#else\nstatic inline void lru_gen_shrink_lruvec_full(")
assert "if (sc->nr_reclaimed != start_reclaimed)\n\t\tWRITE_ONCE(lruvec->evictable.reclaim_backoff_until, 0);" in reclaim
assert "current_is_kswapd() &&\n\t\t     sc->nr_scanned - start_scanned >= SWAP_CLUSTER_MAX" in reclaim
assert "if (sc->nr_scanned == start_scanned ||" in reclaim
assert "msecs_to_jiffies(50)" in reclaim
assert "sc->nr_reclaimed - start_reclaimed < sc->nr_to_reclaim" in reclaim
assert "(unsigned long)SWAP_CLUSTER_MAX * 4" in v

# Keep the experimental 4.4 backport opt-in; preserve zRAM + reclaim ABI.
assert "CONFIG_LRU_GEN=y" in cfg
assert "# CONFIG_LRU_GEN_ENABLED is not set" in cfg
assert "CONFIG_ZRAM=y" in cfg
assert "CONFIG_ZSWAP_MIGRATION_SUPPORT=y" in cfg
assert "static bool lru_gen_ptwalk_runtime;" in v
assert "static bool lru_gen_scan_around_runtime;" in v

print("PASS: per-zone MGLRU page selection and oldest budget lock snapshots")
print("PASS: runtime OFF transition cannot recycle generation during aging")
print("PASS: kswapd no-progress retry guard while direct reclaim remains responsive")
print("PASS: MGLRU remains default OFF (R8 user request) with bounded opt-in aging")
print("NOTE: compile + device stress + pstore/PSI/LMKD evidence required")
