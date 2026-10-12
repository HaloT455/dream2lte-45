#!/usr/bin/env python3
from pathlib import Path
p = Path("scripts/alice-v12r69-mglru-postboot.sh").read_text()
assert "getprop sys.boot_completed" in p
assert "sleep 15" in p
assert "/system/bin/init.mglru.sh" in p
assert '[ "$(cat "$SYS" 2>/dev/null)" = "0" ] || exit 0' in p
assert 'echo 1 > "$SYS"' in p
assert "while true" not in p
assert "\\n" not in p, "escaped newline corruption is not permitted in shell source"
assert "echo 0 >" not in p
assert "setprop persist.device_config.lmkd_native" not in p
print("PASS: guarded one-shot post-boot restore; no malformed shell escape")
