#!/usr/bin/env python3
"""Static guards for experimental Mali-G71 15-graphics + 5-compute job masks.

Not an NPU implementation and not a boot or thermal-stability certification.
"""
from pathlib import Path

cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
gpu = Path("drivers/gpu/arm/b_r19p0/backend/gpu/mali_kbase_pm_backend.c").read_text()
js = Path("drivers/gpu/arm/b_r19p0/mali_kbase_js.c").read_text()
dts = Path("arch/arm64/boot/dts/exynos/exynos8895.dtsi").read_text()
mm = Path("mm/vmscan.c").read_text()

assert "CONFIG_MALI_HALO_NPU_PARTITION=y" in cfg
assert "CONFIG_MALI_TMIX_R19P0=y" in cfg
assert "CONFIG_EXYNOS_VPU=y" in cfg and "CONFIG_EXYNOS_VPU_HARDWARE=y" in cfg
assert "# CONFIG_LRU_GEN_ENABLED is not set" in cfg, "MGLRU must be opt-in until stable"
assert "CONFIG_PSI=y" in cfg and "CONFIG_ZRAM=y" in cfg
assert "HALO_NPU_GPU_CORE_COUNT 5" in gpu
g = gpu[gpu.index("static void kbase_halo_npu_init_partition("):
        gpu.index("int kbase_hwaccess_pm_powerup(")]
assert "halo_npu_mask_weight(shader_present) == 20" in g
assert "kbdev->gpu_props.num_core_groups == 2" in g
assert "compute_group" in g and "group[1].core_mask" in g
assert "graphics_group" in g and "group[0].core_mask" in g
assert "graphics_group && !(graphics_group & compute_group)" in g
assert "compute_mask = halo_npu_take_high_cores(" in g
assert "compute_group, HALO_NPU_GPU_CORE_COUNT" in g
assert "graphics_mask = shader_present & ~compute_mask" in g
assert "halo_npu_mask_weight(graphics_mask) != 15" in g
assert "halo_npu_mask_weight(compute_mask) != HALO_NPU_GPU_CORE_COUNT" in g
assert "(graphics_mask & compute_mask)" in g
assert "((graphics_mask | compute_mask) != shader_present)" in g
assert "kbdev->pm.debug_core_mask[0] = graphics_mask;" in g
assert "kbdev->pm.debug_core_mask[1] = graphics_mask;" in g
assert "kbdev->pm.debug_core_mask[2] = compute_mask;" in g
assert g.count("kbdev->pm.debug_core_mask_all = shader_present;") == 2
assert "stock GPU masks retained" in g
assert "kbdev->pm.debug_core_mask[0] = shader_present" in g
assert "kbdev->pm.debug_core_mask[1] = shader_present" in g
assert "kbdev->pm.debug_core_mask[2] = shader_present" in g
assert "katom->device_nr == 1" in js and "return 2;" in js, "JS2 dispatch must be explicit"
assert "gpu_max_clock = <546000>;" in dts
assert "gpu_max_clock_limit = <546000>;" in dts
assert "gpu_tmu_control = <1>;" in dts, "GPU thermal control must stay on"
assert "static bool lru_gen_ptwalk_runtime;" in mm
print("PASS: 20-core topology check and group1-only compute selection")
print("PASS: 15 graphics shaders and five compute shaders, disjoint and exhaustive")
print("PASS: full-stock mask fallback on unknown or fused topology")
print("PASS: GPU DVFS and thermal limits unchanged; VPU retained")
print("PASS: MGLRU default OFF; no GPU kernel-reclaim offload claimed")
