#!/usr/bin/env python3
"""Verify user-controllable ALICE kernel telemetry without unsafe NPU/MGLRU claims."""
from pathlib import Path
c = Path("kernel/alice_sysintel.c").read_text()
a = Path("alice/android-app/app/src/main/java/com/halot455/alice/MainActivity.java").read_text()
cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
for value in (
    'kobject_create_and_add("alice", kernel_kobj)',
    '__ATTR(mode, 0644, mode_show, mode_store)',
    '__ATTR(policy_enabled, 0644,',
    '__ATTR_RO(capabilities)',
    '__ATTR_RO(assessment)',
    '__ATTR_RO(vm_policy)',
    'alice_saved_swappiness = READ_ONCE(vm_swappiness);',
    'if (READ_ONCE(vm_swappiness) == alice_applied_swappiness)',
    'WRITE_ONCE(vm_swappiness, alice_saved_swappiness);',
    'mglru_offload=0 mglru_auto_enable=0',
    'default_stability=1',
    'return -EBUSY;',
    'model_inference=0',
):
    assert value in c, value
for value in (
    '/sys/kernel/alice/assessment',
    '/sys/kernel/alice/capabilities',
    '/sys/kernel/alice/vm_policy',
    '/sys/kernel/alice/mode',
    '/sys/kernel/alice/policy_enabled',
    'KernelSU',
    'featureMatrix()',
    'GPU+VPU inference hợp nhất / NPU thật',
):
    assert value in a, value
assert 'CONFIG_ALICE_SYSINTEL=y' in cfg
assert 'CONFIG_LRU_GEN_ENABLED=y' in cfg, 'V12R66 boot experiment must start MGLRU ON'
assert 'CONFIG_EXYNOS_VPU_HARDWARE=y' in cfg
assert 'CONFIG_MALI_HALO_NPU_PARTITION=y' in cfg
assert 'new ProcessBuilder("su", "-c", command)' in a
assert 'echo 1 > /sys/kernel/mm/lru_gen/enabled' not in a
print("PASS: ALICE V12R61 system bridge/profile, bounded opt-in rollback and Android UI")
print("PASS: V12R66 MGLRU boot ON research configuration, no model/VPU offload claim")
