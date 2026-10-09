# V12R5R — zram/zsmalloc non-LRU CMA migration fix (EXPERIMENTAL)

## Findings in V12R5Q log

- 18 samples, same boot ID, kernel Enforcing, MGLRU OFF.
- `ion_crypto`: 2/2 failed requests for 6 MiB, 9218 CMA `-EBUSY`
  retries and 0 live ION crypto buffers.
- Global failure-state buckets: 7047 non-LRU, 11 LRU out of 7058
  failed page-isolation checks; no reserved/slab/compound/HWPoison.
- All **600 available** `dump_page` mapping pointers had lower two bits
  equal to 2. On this kernel `PAGE_MAPPING_MOVABLE=0x2`, which
  identifies the special non-LRU movable page mapping.
- Dmesg also recorded a **separate** order-6 (`256 KiB`) GPU
  hardware-counter allocation failure for `gpuwatchapp` at 347.694s.
- A mapping bit pattern indicates a non-LRU movable page, not
  conclusively which subsystem owns it; zsmalloc is the likely owner
  because this tree tags its pages with `__SetPageMovable`.

## Root cause candidate and fix

`mm/zsmalloc.c` unconditionally tags allocated zspages as movable
under `CONFIG_COMPACTION`, but `mm/compaction.c` scans non-LRU
movable pages only if `CONFIG_ZSWAP_MIGRATION_SUPPORT=y`.
`mm/zsmalloc.c` also leaves `zs_page_migration_enabled=0` if this
config option is unset.

The previous Kconfig made this option depend on `ZSWAP`, even though
**ZRAM uses zsmalloc and is enabled on this machine**. Therefore
compaction skips these movable pages and CMA cannot isolate them.

V12R5R makes this existing option selectable for
`(ZSWAP || ZRAM) && ZSMALLOC && COMPACTION` and enables it in the
Galaxy S8+ defconfig. The original `isolate_movable_page`,
`zs_page_isolate`, `zs_page_migrate`, `putback_movable_page` path
is used; **no new migration algorithm** is written. ZSWAP remains
disabled. No CMA size, secure heaps, MGLRU, zram capacity, scheduler,
SELinux, DTB or ramdisk policy changes.

### Risks

The zsmalloc migration path was dormant in the previous configuration.
It must be treated as **experimental** until actual boot and workload
tests confirm no corruption, crash, hang, excessive CPU cost or loss
of saved state. A successful build does not prove migration correctness.
Keep a working V12R5Q backup boot; do not enable MGLRU.

## Test after successful V12R5R boot (without stress)

1. Verify `uname -r`, `getenforce`, `sys.boot_completed=1`,
   `/sys/kernel/mm/lru_gen/enabled=0`.
2. Measure `/sys/class/ion_cma/ion_crypto/diagnostics`, its
   `cma_busy_retries_region`, `alloc_dma_failed`, and
   `isolation_*_global` 18 times during normal usage.
3. Check dmesg for `Bad page state`, kernel panic, `BUG`,
   migration errors, `PFNs busy`, and `Fail to allocate buffer`.
4. Compare retries and 6-MiB allocation outcome to V12R5Q.
   No active retry during sampling is not evidence the original crypto
   initialization succeeded; a boot-time `alloc_success>0` is expected
   if the same workload is performed and allocation reaches this heap.

`non_lru` bucket values are cumulative; they do not mean 7047 unique
physical pages, and the counters are global snapshots.
