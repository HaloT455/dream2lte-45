#!/usr/bin/env python3
"""V12R5W safe boot isolation: DO NOT misrepresent GPU shader masks as an NPU.

This regression test checks that Mali and VPU remain compiled, but the
unvalidated JS2-only five-shader mask experiment is disabled. MGLRU is still
an opt-in CPU memory management feature and NEVER a GPU/VPU work queue.
Passing these checks or the CI build does not prove a device can boot.
"""
from pathlib import Path

cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
gpu = Path("drivers/gpu/arm/b_r19p0/backend/gpu/mali_kbase_pm_backend.c").read_text()
vmscan = Path("mm/vmscan.c").read_text()

assert "# CONFIG_MALI_HALO_NPU_PARTITION is not set" in cfg
assert "CONFIG_MALI_TMIX_R19P0=y" in cfg
assert "CONFIG_EXYNOS_VPU=y" in cfg
assert "CONFIG_EXYNOS_VPU_HARDWARE=y" in cfg
assert "CONFIG_EXYNOS_VPU_EXYNOS8895=y" in cfg

assert "CONFIG_LRU_GEN=y" in cfg
assert "# CONFIG_LRU_GEN_ENABLED is not set" in cfg
assert "CONFIG_ZRAM=y" in cfg
assert "CONFIG_PSI=y" in cfg

# Retain original HALO mask code guarded by a config, but remove it from
# the boot image so JS0, JS1 and JS2 use the normal shader-present mask.
assert "#ifdef CONFIG_MALI_HALO_NPU_PARTITION" in gpu
assert "kbase_halo_npu_init_partition(kbdev);" in gpu
assert "kbdev->gpu_props.props.raw_props.shader_present;" in gpu
assert "static bool lru_gen_ptwalk_runtime;" in vmscan
assert "static bool lru_gen_scan_around_runtime;" in vmscan

print("PASS: normal Mali shader mask; no synthetic five-core NPU partition")
print("PASS: Samsung VPU driver unchanged")
print("PASS: MGLRU stays OFF at boot; zRAM/PSI retained")
print("NOTE: this is a boot-isolation candidate, not evidence of NPU offload")
