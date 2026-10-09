#!/usr/bin/env python3
"""V12R5P source contract checks. Static only; kernel CI tests compile."""
from pathlib import Path

heap = Path("drivers/staging/android/ion/ion_cma_heap.c").read_text()
ion = Path("drivers/staging/android/ion/exynos/exynos_ion.c").read_text()
priv = Path("drivers/staging/android/ion/ion_priv.h").read_text()
cma = Path("mm/cma.c").read_text()
cmah = Path("mm/cma.h").read_text()
config = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()

assert "CONFIG_CMA=y" in config  # Input defconfig; CI checks resolved .config
assert "CONFIG_DMA_CMA=y" in config and "CONFIG_CMA=y" in config
assert "__ATTR_RO(diagnostics)" in ion
assert "device_create_file(dev, &cma_diag_attr)" in ion
assert "ion_cma_diag_show(pdata->heap, buf)" in ion
assert "ssize_t ion_cma_diag_show(struct ion_heap *heap, char *buf)" in priv

for marker in ("alloc_requests", "alloc_success", "alloc_failed",
               "alloc_dma_failed", "live_buffers", "live_bytes",
               "last_failed_bytes", "last_dma_failed_bytes", "last_errno",
               "cma_bytes_region", "cma_busy_retries_region",
               "cma_failed_requests_region"):
    assert marker + "=%" in heap, marker
assert "atomic64_inc(&cma_heap->diag_dma_failed)" in heap
assert "atomic64_add(PAGE_ALIGN(size), &cma_heap->diag_live_bytes)" in heap
assert "atomic64_sub(PAGE_ALIGN(size), &cma_heap->diag_live_bytes)" in heap
assert "atomic64_inc(&cma_heap->diag_alloc_failed)" in heap

# One per -EBUSY returned to cma_alloc, and one failure per overall request.
assert "atomic64_inc(&cma->diag_busy_retries);" in cma
assert "if (ret != -EBUSY)" in cma
assert cma.index("if (ret != -EBUSY)") < cma.index("atomic64_inc(&cma->diag_busy_retries)")
assert "if (!page)\n\t\tatomic64_inc(&cma->diag_failed_requests)" in cma
assert "atomic64_t diag_busy_retries;" in cmah
assert "atomic64_t diag_failed_requests;" in cmah

# No new sysfs writes, physical page identifiers, or unsupported debugfs mount.
assert "DEVICE_ATTR_RW" not in ion
assert "sysfs_create_file" not in heap
assert "page_to_phys" not in heap[heap.index("ssize_t ion_cma_diag_show"):heap.index("struct ion_heap *ion_cma_heap_create")]
print("PASS: V12R5P CMA/ION instrumentation source invariants")
print("NOTE: requires successful build and boot before trusting runtime counters")
