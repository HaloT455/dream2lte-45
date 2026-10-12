#!/usr/bin/env python3
from pathlib import Path
p=Path("scripts/alice-v12r69-mglru-postboot.sh").read_text()
assert 'getprop sys.boot_completed' in p
assert 'sleep 15' in p
assert '/system/bin/init.mglru.sh' in p
assert '[ "$(cat "$SYS" 2>/dev/null)" = "0" ] || exit 0' in p
assert 'echo 1 > "$SYS"' in p
assert 'while true' not in p
assert 'lmkd' not in p.lower().replace('never modifies lmkd','')
print("PASS: one-shot, post-boot, no polling loop, double-check before write")
