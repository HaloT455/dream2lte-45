#!/usr/bin/env python3
"""Static regression checks for the V12R5M Samsung 4.4 MGLRU reclaim bridge.

These checks intentionally do not claim runtime stability. Hardware stress and
pstore review are required after a successful kernel build.
"""
from pathlib import Path

vmscan = Path("mm/vmscan.c").read_text()
mmzone = Path("include/linux/mmzone.h").read_text()

checks = {
    "only-oldest reclaim budget": "eligible = lru_gen_oldest_pages(lruvec, 1)" in vmscan,
    "read older anon on allowed swappiness": "eligible += lru_gen_oldest_pages(lruvec, 0)" in vmscan,
    "list membership check": "empty = list_empty(&lrugen->lists[gen][type][zid])" in vmscan,
    "size-list inconsistency trace": "empty oldest list with size=%lu" in vmscan,
    "bounded reclaim work": "(unsigned long)SWAP_CLUSTER_MAX * 4" in vmscan,
    "time-bounded failed-reclaim retry": "reclaim_backoff_until" in mmzone and "time_before(jiffies" in vmscan,
    "avoid false eligible reporting": "*lru_pages = 0;" in vmscan,
    "new counters for APK": "backoffs=%lld empty_oldest=%lld" in vmscan,
    "cooldown initialized": "lrugen->reclaim_backoff_until = 0;" in vmscan,
    "full generation-aware reclaim kept": "lru_gen_reclaim_batch(lruvec, sc, type" in vmscan,
}
for name, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL'}: {name}")
if not all(checks.values()):
    raise SystemExit(1)
print("Static MGLRU regression checks passed; runtime validation still required.")
