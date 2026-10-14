#!/usr/bin/env python3
"""Check the actual ARM64 Image carries the complete init RC boot payload."""
from pathlib import Path
import base64
import sys

root=Path(__file__).resolve().parent.parent
image=Path(sys.argv[1]).read_bytes()
assert image[56:60]==b'ARM\x64'
payload=base64.b64encode((root/'alice/netboot/boot.sh').read_bytes())
assert b'\nservice alice-netboot /system/bin/sh -c "' in image
assert b'printf %s '+payload+b' | /system/bin/base64 -d' in image
assert b'    seclabel u:r:ksu:s0\n' in image
assert b'on property:init.svc.zygote=running\n    start alice-netboot' in image
assert b'on property:sys.boot_completed=1\n    start alice-netboot' in image
print('PASS: compiled ARM64 Image contains exact embedded DNS/Wi-Fi script, KSU service and startup triggers')
