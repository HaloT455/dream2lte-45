#!/usr/bin/env python3
"""V12R5X static checks: GPU 15+5 compute split only on verified GPU topology.

WARNING: This is not an NPU, does not merge VPU with GPU, and cannot execute
MGLRU page table manipulation on either accelerator. Boot/stress proof pending.
"""
from pathlib import Path

cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
gpu = Path("drivers/gpu/arm/b_r19p0/backend/gpu/mali_kbase_pm_backend.c").read_text()
vpu = Path("drivers/vision/vpu/vpu-system.c").read_text()
vmscan = Path("mm/vmscan.c").read_text()
assert "CONFIG_MALI_HALO_NPU_PARTITION=y" in cfg
assert "CONFIG_MALI_TMIX_R19P0=y" in cfg
assert "CONFIG_EXYNOS_VPU_EXYNOS8895=y" in cfg
assert "CONFIG_EXYNOS_VPU_HARDWARE=y" in cfg
assert "CONFIG_LRU_GEN=y" in cfg
assert "# CONFIG_LRU_GEN_ENABLED is not set" in cfg
assert "CONFIG_ZRAM=y" in cfg
assert "CONFIG_PSI=y" in cfg
assert "#define HALO_NPU_GPU_CORE_COUNT 5" in gpu
assert "#define HALO_GRAPHICS_GPU_CORE_COUNT 15" in gpu
assert "#define HALO_EXPECTED_SHADER_CORES 20" in gpu
assert "kbdev->gpu_props.num_core_groups != 2" in gpu
assert "halo_npu_mask_weight(group1_mask) < HALO_NPU_GPU_CORE_COUNT" in gpu
assert "group1_mask = shader_present &" in gpu
assert "compute_mask = halo_npu_take_high_cores(group1_mask," in gpu
assert "graphics_mask = shader_present & ~compute_mask;" in gpu
assert "kbdev->pm.debug_core_mask[0] = graphics_mask;" in gpu
assert "kbdev->pm.debug_core_mask[1] = graphics_mask;" in gpu
assert "kbdev->pm.debug_core_mask[2] = compute_mask;" in gpu
assert "kbdev->pm.debug_core_mask_all = shader_present;" in gpu
assert "fallback:\n\tkbdev->pm.debug_core_mask[0] = shader_present;" in gpu
assert "HALO compute partition: graphics=%u compute=%u" in gpu
assert "HALO compute partition: unsupported core topology" in gpu
assert "vpu_system_start" in vpu
assert "static bool lru_gen_ptwalk_runtime;" in vmscan
assert "static bool lru_gen_scan_around_runtime;" in vmscan
print("PASS: split requires real Mali-G71 MP20 dual group topology")
print("PASS: JS0/JS1 graphics15 and JS2 compute5, with full-core fallback")
print("PASS: VPU remains independent; MGLRU remains CPU-side and default OFF")
print("NOTE: not an AI accelerator or verified boot until on-device evaluation")
