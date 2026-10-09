# V12R5Q — classify failed isolation page states (no reclaim changes)

Derived from **V12R5P ION/CMA diagnostics**; the S8+ booted V12R5P with
MGLRU disabled. It logged repeated `__alloc_contig_range PFNs busy`, with
`ion_crypto` returning `-ENOMEM` on 6 MiB DMA/CMA requests.

## What changes

Only counters and a snapshot getter were added to
`mm/page_isolation.c`. No alteration to page isolation, migration,
compaction, reclaim, SELinux, secure memory, CMA reservation, MGLRU,
or scheduler. No new log spam. Existing `dump_page` remains intact.

When `__test_page_isolated_in_pageblock` finds a page that is not free/
isolated, it records exactly one bucket for that **first** page:

- `isolation_reserved_pages_global`
- `isolation_hwpoison_pages_global`
- `isolation_slab_pages_global`
- `isolation_compound_pages_global`
- `isolation_lru_pages_global`
- `isolation_non_lru_pages_global`

`isolation_failed_checks_global` is the sum of the buckets (subject to
non-atomic snapshot reads), and `isolation_pageblock_mismatch_global`
counts checks failing before the page-by-page scan because a pageblock
was not isolated or no valid starting page was found.

The fields are appended to the existing read-only
`/sys/class/ion_cma/ion_crypto/diagnostics` (also video_stream and tui).

**All `*_global` fields are machine-wide counts:** checks from other
CMA regions and non-CMA users may contribute; reading the counters through
one heap does not make them heap-specific. A page observed as non-LRU
is **not proof** of permanent pinning or of an offending process. Counts
can be high when one allocation retries many times.

## Safe baseline command after a successful V12R5Q boot

```bash
adb shell uname -r
adb shell getenforce
adb shell "su -c 'cat /sys/kernel/mm/lru_gen/enabled'"
adb shell "su -c 'cat /sys/class/ion_cma/ion_crypto/diagnostics'"
adb shell "su -c 'cat /sys/class/ion_cma/ion_video_stream/diagnostics'"
adb shell "su -c 'cat /sys/class/ion_cma/ion_tui/diagnostics'"
adb shell "su -c 'grep -E \"CmaTotal:|CmaFree:|MemAvailable:\" /proc/meminfo'"
adb exec-out su -c dmesg > V12R5Q-dmesg.txt
```

Keep MGLRU OFF. Do not run memory stress workloads until
separate code review and controlled safety testing.
