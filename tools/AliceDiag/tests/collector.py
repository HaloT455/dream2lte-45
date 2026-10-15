#!/usr/bin/env python3
"""Execute the periodic script with external commands instrumented, not just a text check."""
import subprocess
from pathlib import Path

script = Path('tools/AliceDiag/app/src/main/assets/sample.sh').read_text()
functions = '\n'.join(f'{name}() {{ printf "\\nUNEXPECTED_EXTERNAL_{name}\\n"; return 99; }}' for name in ['cat', 'awk', 'dumpsys', 'head', 'getprop', 'uname', 'sha256sum', 'settings', 'setprop', 'mount', 'chmod', 'chown'])
for detail in [0, 1]:
    # The only optional periodic external command is one ps, once per detailed sample.
    prefix = f'detail={detail}\n' + functions + '\nps() { printf "\\nEXPECTED_PS\\n"; }\n'
    result = subprocess.run(['sh'], input=prefix + script, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'UNEXPECTED_EXTERNAL_' not in result.stdout, result.stdout[-3000:]
    assert result.stdout.count('EXPECTED_PS') == detail
    assert '@@ /proc/stat' in result.stdout and '@@ /proc/meminfo' in result.stdout
print('PASS: periodic fast path has no external reader/dumpsys process; detailed path uses one ps')
