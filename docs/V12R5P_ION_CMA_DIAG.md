# V12R5P: read-only ION/CMA diagnostics

Derived from V12R5O. This change does not alter CMA reservation sizes, page
migration/reclaim decisions, SELinux, MGLRU enablement, or secure ION memory.

## Why

The S8+ showed `crypto: Fail to allocate buffer`, ION `len 6291456`
`-ENOMEM`, and `__alloc_contig_range ... PFNs busy` while MGLRU was
disabled. `CmaFree` alone cannot distinguish pinned/immovable pages,
another allocator's live buffers, or non-ION CMA users.

## Read-only sysfs files

Each Exynos reusable ION DMA/CMA region already has a sysfs device:

- `/sys/class/ion_cma/ion_crypto/diagnostics`
- `/sys/class/ion_cma/ion_video_stream/diagnostics`
- `/sys/class/ion_cma/ion_tui/diagnostics`

The file mode is **0444**. Counters start at boot (no reset/write interface).
`CONFIG_DEBUG_FS` stays disabled. No physical addresses, PID, handles,
allocation contents, or security state are exposed.

### Per-heap fields

- `alloc_requests`: invocations of this ION DMA heap's allocate callback.
- `alloc_success`, `alloc_failed`: success/failure of the complete
  allocation, including secure protection and metadata setup.
- `alloc_dma_failed`: calls where `dma_alloc_from_contiguous` returned NULL.
- `live_buffers`, `live_bytes`: successful allocations not yet freed by
  this ION heap. Bytes include page/protection alignment.
- `last_failed_bytes`: requested ION bytes in last failed request.
- `last_dma_failed_bytes`: physical CMA bytes requested in most recent
  `dma_alloc_from_contiguous` failure.
- `last_errno`: last ION heap failure code.

### CMA region fields

- `cma_bytes_region`: reserved size for the CMA area attached to this heap.
- `cma_busy_retries_region`: number of `alloc_contig_range` `-EBUSY`
  attempts on the CMA area (one allocation can generate multiple retries).
- `cma_failed_requests_region`: CMA requests that returned no page.
  Includes both bitmap exhaustion and migration failures.

**Important:** Region counters also include non-ION callers sharing a CMA area.
Multiple ION heaps could expose the same region counter. The kernel does not
infer the cause of a pinned page from these counters.

## Capture on Zorin OS (do not enable MGLRU)

```bash
adb shell "su -c 'cat /sys/kernel/mm/lru_gen/enabled'"
adb shell "su -c 'for d in /sys/class/ion_cma/ion_*; do
  echo ==== $d ====
  cat $d/region_name $d/region_id $d/diagnostics
done'"
adb shell "su -c 'grep -E "CmaTotal:|CmaFree:|MemAvailable:" /proc/meminfo'"
adb exec-out su -c 'dmesg' > V12R5P-dmesg.txt
```

This is a diagnostic kernel, not evidence that V12R5O's generation-accounting
fix resolves `empty_oldest`. Keep `/sys/kernel/mm/lru_gen/enabled` at 0
until separate, controlled testing.
