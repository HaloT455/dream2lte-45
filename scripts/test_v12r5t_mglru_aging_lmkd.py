#!/usr/bin/env python3
"""V12R5T static regression checks. Runtime testing is still mandatory."""
from pathlib import Path

v = Path("mm/vmscan.c").read_text()
w = Path("mm/workingset.c").read_text()
cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()

assert "CONFIG_LRU_GEN=y" in cfg
assert "# CONFIG_LRU_GEN_ENABLED is not set" in cfg, "experimental MGLRU must default OFF"
assert "CONFIG_ZSWAP_MIGRATION_SUPPORT=y" in cfg
assert "static bool lru_gen_ptwalk_runtime;" in v, "page-table aging must be opt-in"
assert "__ATTR(ptwalk, 0644, lru_gen_ptwalk_show, lru_gen_ptwalk_store)" in v
assert "current_is_kswapd() &&" in v, "no full-mm PTE walk from direct reclaim"
assert "lru_gen_age_lruvec_legacy(lruvec, sc, swappiness);" in v
assert "lru_gen_ptwalk_retry_after" in v
assert "msecs_to_jiffies(250)" in v
assert "2UL * 1024 * 1024" in v, "limit page-table sampling window"
assert "mm->map_count" in v
assert "walk_page_range(start, end, &walk)" in v
assert "ptwalk_rounds=%lld" in v
assert "lru_gen_reclaim_batch(lruvec, sc, type" in v
assert "lru_gen_scan_around(&pvmw);" in Path("mm/rmap.c").read_text()
refault = w[w.index("void lru_gen_refault(struct page *page, void *shadow)"):]
refault = refault[:refault.index("#endif /* CONFIG_LRU_GEN */")]
assert refault.count("inc_zone_state(zone, WORKINGSET_REFAULT);") == 1
assert (refault.index("inc_zone_state(zone, WORKINGSET_REFAULT);") <
        refault.index("if (token != (min_seq &"),
        "LMKD should count refault even with stale MGLRU shadow")
assert "atomic_long_add(hpage_nr_pages(page)," in refault
print("PASS: MGLRU opt-in PTE aging is kswapd-only, bounded and rate-limited")
print("PASS: MGLRU refault vmstat precedes generation-token filtering")
print("PASS: default MGLRU OFF; ZRAM CMA migration retained")
print("NOTE: Static checks cannot establish target runtime stability.")
