#!/usr/bin/env python3
"""Execute actual bootstrap/guard against synthetic Android files and commands."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
script = (root/'alice/powerhal/boot.sh').read_text()
old, new = b'audited synthetic original', b'public source service fixture'
digest = lambda b: hashlib.sha256(b).hexdigest()
mock = r'''#!/usr/bin/env python3
import os,sys,json,shutil
from pathlib import Path
name=Path(sys.argv[0]).name;a=sys.argv[1:];base=Path(os.environ['MOCK_ROOT'])
with (base/'calls').open('a') as f:f.write(json.dumps([name]+a)+'\n')
if name==os.environ.get('MOCK_FAIL'):sys.exit(1)
if name=='ls':
 print('u:object_r:'+('sysfs_power' if 'cpufreq_min_limit' in a[-1] else 'hal_power_default_exec')+':s0 '+a[-1]);sys.exit(0)
if name in ['chown','chmod','chcon','sleep','setprop']:sys.exit(0)
if name=='mount':
 assert a[0]=='--bind';shutil.copyfile(a[2],base/'original');shutil.copyfile(a[1],a[2]);sys.exit(0)
if name=='umount':
 # The running HAL retains an executable/mmap reference to the bind mount.
 if a[0]!='-l':sys.exit(16)
 shutil.copyfile(base/'original',a[-1]);sys.exit(0)
if name=='dumpsys':
 if os.environ.get('MOCK_READY')=='1':print('ALICE Power HAL R12 AIDL V2; backend=ready; sessions=16')
 else:print('backend=unavailable')
 sys.exit(0)
raise AssertionError(name)
'''
with tempfile.TemporaryDirectory() as tmp:
    area = Path(tmp)
    bin = area/'bin'
    bin.mkdir()
    for name in ['ls', 'chown', 'chmod', 'chcon', 'mount', 'umount', 'sleep', 'setprop', 'dumpsys']:
        f = bin/name
        f.write_text(mock)
        f.chmod(0o755)
    def run_case(name, ready=True, unknown=False, failure=None):
        p = area/name
        p.mkdir()
        target = p/'vendor/bin/hw/android.hardware.power.samsung-service'
        blob = p/'sys/kernel/alice_powerhal'
        node = p/'sys/power/alice_power_hint'
        rc = p/'vendor/etc/init/power-default-sec.rc'
        manifest = p/'vendor/etc/vintf/manifest/power-samsung.xml'
        for f, data in [(target, b'unknown' if unknown else old), (blob, new), (node, b''),
                        (rc, b'service vendor.samsung.power-default /vendor/bin/hw/android.hardware.power.samsung-service'),
                        (manifest, b'<version>2</version>')]:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
        s = re.sub(r'^OLD_SHA=.*$', 'OLD_SHA='+digest(old), script, flags=re.M)
        for prefix in ['/data/adb/alice-powerhal', '/vendor/bin/hw/android.hardware.power.samsung-service',
                       '/sys/power/alice_power_hint', '/sys/kernel/alice_powerhal',
                       '/vendor/etc/init/power-default-sec.rc', '/vendor/etc/vintf/manifest/power-samsung.xml',
                       '/sys/power/cpufreq_min_limit']:
            # Preserve the service name inside the synthetic rc file.
            s = s.replace(prefix, str(p)+prefix)
        f = p/'boot.sh'
        f.write_text(s)
        env = dict(os.environ, PATH=str(bin)+':'+os.environ['PATH'], MOCK_ROOT=str(p), MOCK_READY='1' if ready else '0')
        if failure: env['MOCK_FAIL'] = failure
        subprocess.run(['sh', str(f)], env=env, check=True)
        state = p/'data/adb/alice-powerhal'
        log = (state/'status.log').read_text()
        if unknown:
            assert 'VENDOR_HASH_UNKNOWN_SKIPPED' in log and target.read_bytes() == b'unknown'
            return
        if failure:
            assert 'POWERHAL_BOUND' not in log and target.read_bytes() == old
            return
        assert 'POWERHAL_BOUND' in log and target.read_bytes() == new
        subprocess.run(['sh', str(f), 'guard'], env=env, check=True)
        log = (state/'status.log').read_text()
        calls = [json.loads(l) for l in (p/'calls').read_text().splitlines()]
        if ready:
            assert 'POWERHAL_RUNTIME_READY' in log and target.read_bytes() == new
            assert not (state/'disable').exists()
            assert not any(c[0] == 'setprop' for c in calls)
        else:
            assert 'POWERHAL_FALLBACK_VENDOR_RESTORED' in log and target.read_bytes() == old
            assert (state/'disable').exists() and node.read_text() == 'reset\n'
            assert sum(c[0] == 'dumpsys' for c in calls) == 6
            assert ['setprop', 'ctl.restart', 'vendor.samsung.power-default'] in calls
            subprocess.run(['sh', str(f)], env=env, check=True)
            assert target.read_bytes() == old
    run_case('ready')
    run_case('fallback', ready=False)
    run_case('unknown', unknown=True)
    run_case('label-failure', failure='chcon')
    run_case('mount-failure', failure='mount')
print('PASS: actual Power HAL bootstrap gates ROM/hash/labels; bounded guard restores vendor and disables failed replacement')
