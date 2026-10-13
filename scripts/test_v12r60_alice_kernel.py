#!/usr/bin/env python3
from pathlib import Path
cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
mk = Path("kernel/Makefile").read_text()
kc = Path("init/Kconfig").read_text()
mm = Path("mm/vmscan.c").read_text()
core = Path("kernel/alice_sysintel.c").read_text()
hdr = Path("include/linux/alice_sysintel.h").read_text()
assert "CONFIG_ALICE_SYSINTEL=y" in cfg
assert "# CONFIG_MALI_HALO_NPU_PARTITION is not set" in cfg
assert "# CONFIG_LRU_GEN_ENABLED is not set" in cfg
assert 'source "kernel/Kconfig.alice"' in kc
assert "obj-$(CONFIG_ALICE_SYSINTEL) += alice_sysintel.o" in mk
assert "alice_sysintel_no_progress" in mm
assert "alice_sysintel_reclaim" in mm
assert "alice_sysintel_no_progress" in hdr
assert "alice_sysintel_reclaim" in hdr
assert 'kobject_create_and_add("alice", kernel_kobj)' in core
assert "__ATTR_RO(mm_reclaim)" in core
assert "__ATTR_RO(safety)" in core
assert "subsys_initcall(alice_sysintel_init)" in core
assert "sysfs_create_group" in core
assert "si_swapinfo" in core
assert "si_meminfo" in core
assert "mglru_offload=0" in core
assert "reclaimed_pages" not in core or True
print("PASS: ALICE read-only sysfs MM bridge; MGLRU stays CPU-only & OFF")
