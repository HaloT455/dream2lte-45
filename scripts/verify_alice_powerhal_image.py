#!/usr/bin/env python3
"""Check the exact CI service and bootstrap in the actual linked ARM64 Image."""
from pathlib import Path
import base64
import hashlib
import sys

root = Path(__file__).resolve().parent.parent
image, elf = map(lambda p: Path(p).read_bytes(), sys.argv[1:3])
assert image[56:60] == b'ARM\x64' and elf[:4] == b'\x7fELF'
assert image.count(elf) == 1, 'exact Power HAL service missing/duplicated in Image'
payload = base64.b64encode((root/'alice/powerhal/boot.sh').read_bytes())
assert b'printf %s '+payload+b' | /system/bin/base64 -d' in image
assert b'# ALICE_POWERHAL_R15\non post-fs-data\n    exec u:r:ksu:s0 root root -- /system/bin/timeout 8' in image
assert b'on property:sys.boot_completed=1\n    start alice-powerhal-guard\n' in image
assert b'service alice-powerhal-guard /system/bin/timeout 25 /system/bin/sh /data/adb/alice-powerhal/boot.sh guard\n' in image
assert b'alice_power_hint' in image and b'alice_powerhal' in image
print('PASS: actual ARM64 Image embeds exact AIDL service and bounded bootstrap; SHA256='+hashlib.sha256(elf).hexdigest())
