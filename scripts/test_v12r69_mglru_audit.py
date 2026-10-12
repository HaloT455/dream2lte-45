#!/usr/bin/env python3
from pathlib import Path
v = Path("mm/vmscan.c").read_text()
assert 'lru_gen: sysfs request %s by pid=%d ppid=%d comm=%s state=%d' in v
assert 'pr_info_ratelimited(' in v
assert 'task_ppid_nr(current)' in v
store = v.split('static ssize_t lru_gen_enabled_store(', 1)[1].split('static struct kobj_attribute lru_gen_enabled_attr', 1)[0]
assert 'if (enable == lru_gen_enabled())' not in store
assert 'lru_gen_set_state(enable, true, false);' in v
transition = v.split('void lru_gen_set_state(bool enable, bool main, bool swap)\n{', 1)[1].split('static int __meminit', 1)[0]
assert transition.index('mutex_lock(&lru_gen_state_mutex)') < transition.index('main = main && enable != lru_gen_enabled();')
advance = v.split('static bool lru_gen_advance_min_locked(', 1)[1].split('static bool lru_gen_inc_max_seq_legacy(', 1)[0]
assert 'if (!lrugen->enabled[type])' in advance
print("PASS: MGLRU requests serialized across conversion; disabled generations cannot advance")
