#!/usr/bin/env python3
from pathlib import Path
v = Path("mm/vmscan.c").read_text()
assert 'lru_gen: sysfs request %s by pid=%d ppid=%d comm=%s state=%d' in v
assert 'pr_info_ratelimited(' in v
assert 'task_ppid_nr(current)' in v
assert 'if (enable == lru_gen_enabled())' in v
assert 'lru_gen_set_state(enable, true, false);' in v
print("PASS: MGLRU state requests are attributable; disable remains available")
