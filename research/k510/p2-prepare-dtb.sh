#!/usr/bin/env bash
# P2A DT chosen parameters only, for an initramfs heartbeat proof.
set -euo pipefail
TREE="$1"
FILE="$TREE/arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
test -s "$FILE"
python3 - "$FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
text=p.read_text()
if 'ALICE_K510_P2_CHOSEN' in text:
    raise SystemExit('P2 chosen already applied: fail closed')
text += '''
/* ALICE_K510_P2_CHOSEN, COMPILER TEST ONLY */
&{/} {
    chosen {
        bootargs = "rdinit=/init loglevel=7 printk.time=1";
    };
};
/* P2 kernel is not hardware boot validated. */
'''
# The &{/} path override requires dtc 1.5+; CI will check this.
p.write_text(text)
print("P2A /chosen rdinit=/init marker staged for DTB compilation")
PY
