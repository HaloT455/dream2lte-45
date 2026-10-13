#!/usr/bin/env python3
from pathlib import Path
p = Path("scripts/alice-v12r69-mglru-postboot.sh").read_text()
assert "manual LRU only" in p
assert 'cat "$SYS"' in p
assert '> "$SYS"' not in p
assert "sleep" not in p and "setprop" not in p
print("PASS: retired postboot entry is read-only and cannot enable MGLRU")
