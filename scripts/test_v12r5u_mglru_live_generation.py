#!/usr/bin/env python3
"""V12R5U non-runtime safety checks for MGLRU page generation sampling.

The Samsung 4.4 V12R5T branch remains frozen at commit
3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3.
Passing this script does NOT establish handset performance or boot safety.
"""
from pathlib import Path

v = Path("mm/vmscan.c").read_text()
cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
pte = v[v.index("static int lru_gen_pte_entry("):
        v.index("static void lru_gen_walk_mm_legacy(", v.index("static int lru_gen_pte_entry("))]
scan = v[v.index("void lru_gen_scan_around("):
         v.index("static bool", v.index("void lru_gen_scan_around("))]

# The mm walk can sleep, so an earlier args->max_seq is not safe for list
# promotion once a later generation has reused that circular list slot.
assert "new_gen = lru_gen_from_seq(args->max_seq)" not in pte
assert "spin_lock_irqsave(&zone->lru_lock, flags)" in pte
assert "new_gen = lru_gen_from_seq(READ_ONCE(lruvec->evictable.max_seq))" in pte
assert pte.index("spin_lock_irqsave(&zone->lru_lock, flags)") < pte.index(
    "new_gen = lru_gen_from_seq(READ_ONCE(lruvec->evictable.max_seq))") < pte.index(
    "lru_gen_promote_accessed_locked(page, lruvec, new_gen)"
)
assert pte.index("spin_unlock_irqrestore(&zone->lru_lock, flags)") > pte.index(
    "lru_gen_promote_accessed_locked(page, lruvec, new_gen)"
)

# Rmap locality scanning can race a runtime OFF toggle; its early unlocked
# check alone is insufficient. Do not touch PTE flags after OFF migration.
guard = "if (!lru_gen_enabled() ||\n\t    !lruvec->evictable.enabled[page_is_file_cache(pvmw->page)])"
assert guard in scan
assert scan.index("spin_lock_irq(&zone->lru_lock)") < scan.index(guard)
assert scan.index(guard) < scan.index(
    "new_gen = lru_gen_from_seq(READ_ONCE(lruvec->evictable.max_seq))"
)
assert "goto unlock_scan_around;" in scan
assert "unlock_scan_around:\n\tspin_unlock_irq(&zone->lru_lock);" in scan

# Keep potentially risky walkers as explicit opt-in until field evidence.
assert "CONFIG_LRU_GEN=y" in cfg
assert "CONFIG_LRU_GEN_ENABLED=y" in cfg
assert "static bool lru_gen_scan_around_runtime;" in v
assert "static bool lru_gen_ptwalk_runtime;" in v
assert "lru_gen_age_lruvec_legacy(lruvec, sc, swappiness)" in v
print("PASS: sampled PTE promotion loads current generation under per-zone LRU lock")
print("PASS: rmap scan-around checks live MGLRU state under per-zone LRU lock")
print("PASS: V12R5U retains default-OFF and bounded opt-in PTE aging")
print("NOTE: physical device stress + persistent logs still required")
