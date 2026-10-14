#!/usr/bin/env python3
"""V12R67 static guard: targeted One UI 8 early-init write compatibility.

These checks do NOT prove Samsung boot behavior or kernel runtime stability.
"""
from pathlib import Path
v = Path("mm/vmscan.c").read_text()
cfg = Path("arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text()
a = Path("kernel/alice_sysintel.c").read_text()
assert "# CONFIG_LRU_GEN_ENABLED is not set" in cfg
assert "lru_gen_early_shell_off_ignored = ATOMIC_INIT(0)" in v
assert "time_before(jiffies, msecs_to_jiffies(60000))" in v
assert '!strcmp(current->comm, "sh")' in v
assert "task_ppid_nr(current) == 1" in v
assert "atomic_cmpxchg(&lru_gen_early_shell_off_ignored, 0, 1) == 0" in v
assert "lru_gen_set_state(enable, true, false);" in v
assert "static struct kobj_attribute lru_gen_boot_compat_attr" in v
assert "&lru_gen_boot_compat_attr.attr" in v
assert "runtime_off_allowed=1" in v
assert "IS_ENABLED(CONFIG_LRU_GEN_ENABLED)" in a
assert "#ifdef CONFIG_LRU_GEN_ENABLED" in v
print("PASS: one-shot boot exception limited to first init shell OFF (<60s) on ON-default builds")
print("PASS: ordinary runtime OFF remains reachable through lru_gen_set_state")
print("WARNING: static test does not prove thermals, boot safety or runtime reclaim stability")
