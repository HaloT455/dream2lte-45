#!/usr/bin/env python3
"""V12R5Q static checks: diagnostics only, no changes to isolation decisions."""
from pathlib import Path

mm = Path("mm/page_isolation.c").read_text()
hdr = Path("include/linux/page-isolation.h").read_text()
ion = Path("drivers/staging/android/ion/ion_cma_heap.c").read_text()
sysfs = Path("drivers/staging/android/ion/exynos/exynos_ion.c").read_text()
workflow = Path(".github/workflows/build.yml").read_text()

assert "struct page_isolation_diag_stats" in hdr
assert "void page_isolation_get_diag" in hdr and "void page_isolation_get_diag" in mm
assert "page_isolation_record_failed_page(pfn_to_page(pfn));" in mm
assert mm.count("page_isolation_record_failed_page(pfn_to_page(pfn));") == 1
assert "atomic64_inc(&isolate_diag_block_mismatch);" in mm
assert "if ((pfn < end_pfn) || !page)" in mm
for label in ("reserved", "hwpoison", "slab", "compound", "lru", "non_lru"):
    assert f"atomic64_inc(&isolate_diag_{label});" in mm, label
for label in ("isolation_failed_checks_global", "isolation_reserved_pages_global",
              "isolation_hwpoison_pages_global", "isolation_slab_pages_global",
              "isolation_compound_pages_global", "isolation_lru_pages_global",
              "isolation_non_lru_pages_global",
              "isolation_pageblock_mismatch_global"):
    assert label + "=%llu" in ion, label
assert "page_isolation_get_diag(&isolation)" in ion
assert "__ATTR_RO(diagnostics)" in sysfs
# The instrumentation must not replace the original free-page logic:
assert "if (PageBuddy(page))" in mm
assert "ret = __test_page_isolated_in_pageblock(start_pfn, end_pfn," in mm
assert "return ret ? 0 : -EBUSY;" in mm
# No added debugfs requirement, no writable diagnostic knob.
assert "DEBUG_FS" not in ion
assert "DEVICE_ATTR_RW(diagnostics)" not in sysfs
print("PASS: V12R5Q diagnostics instrumentation source invariants")
print("NOTE: page categories are state snapshots, not proof of pinning or root cause")
