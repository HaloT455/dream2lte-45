#!/usr/bin/env python3
"""Run the one-shot LMKD service against healthy/unsupported/failure cases."""
from pathlib import Path
import os
import subprocess
import tempfile

module=Path('alice/memory-module')
assert (module/'low-swap.sh').read_bytes()==Path('scripts/alice-v12r69-low-swap.sh').read_bytes()
with tempfile.TemporaryDirectory(prefix='r8-service-') as tmp:
    root=Path(tmp); bin=root/'bin'; bin.mkdir()
    (root/'service.sh').write_bytes((module/'service.sh').read_bytes())
    (root/'low-swap.sh').write_text('''#!/bin/sh
echo "$1" >> "$TEST_CALLS"
case "$1" in restore) exit "${RESTORE_CODE:-0}";; apply) exit "${APPLY_CODE:-0}";; esac
''')
    commands={
        'uname':'printf "%s\\n" "${TEST_KERNEL:-4.4.302-Alice-V12R69-R8-ENERGYSTEP-KSU32590-Enf}"',
        'getprop':'''case "$1" in
sys.boot_completed) echo 1;;
sys.lmk.slmk_16up_swap_free_low_percentage) printf '%s\\n' "$TEST_THRESHOLD";;
esac''',
    }
    for name,body in commands.items():
        p=bin/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
    env={**os.environ,'PATH':str(bin)+':'+os.environ['PATH'],'TEST_CALLS':str(root/'calls')}
    # PSI path is checked on device; substitute a readable host fixture.
    fixture=root/'pressure';fixture.write_text('some avg10=0.00\n')
    service=(root/'service.sh').read_text().replace('/proc/pressure/memory',str(fixture))
    (root/'service.sh').write_text(service)
    def run(threshold,extra=None):
        (root/'calls').write_text('')
        subprocess.run(['sh',str(root/'service.sh')],env=env|{'TEST_THRESHOLD':threshold}|(extra or {}),check=True,timeout=5)
        return (root/'calls').read_text().splitlines(),(root/'status.log').read_text()
    assert run('78')[0]==['restore','status','apply','status']
    assert run('78',{'TEST_KERNEL':'4.4.302-Alice-V12R69-R9-ENERGYSTEP-KSU32590-Enf'})[0]==['restore','status','apply','status']
    assert run('78',{'TEST_KERNEL':'4.4.302-Alice-V12R69-R10-ENERGYSTEP-KSU32590-Enf'})[0]==['restore','status','apply','status']
    assert run('78',{'TEST_KERNEL':'4.4.302-Alice-V12R69-R11-ENERGYSTEP-KSU32590-Enf'})[0]==['restore','status','apply','status']
    assert run('10')[0]==['restore','status']
    assert run('')[0]==['restore','status']
    assert run('oops')[0]==['restore','status']
    assert run('78',{'TEST_KERNEL':'other-kernel'})[0]==[]
    assert run('78',{'RESTORE_CODE':'6'})[0]==['restore']
    calls,log=run('78',{'APPLY_CODE':'8'})
    assert calls==['restore','status','apply','status'] and 'ALICE_LOW_SWAP_RESULT=8' in log
print('PASS: one-shot LMKD service preserves healthy/unknown thresholds and skips other kernels')
print('PASS: restore conflict stops apply; incompatibility is reported without a retry loop')
