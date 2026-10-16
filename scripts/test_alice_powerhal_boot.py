#!/usr/bin/env python3
"""Run the actual bootstrap with simulated early-boot IO and mount ownership."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
test_shell = os.environ.get('ALICE_TEST_SHELL', 'sh')
print('Bootstrap test shell:', test_shell, flush=True)
script = (root/'alice/powerhal/boot.sh').read_text()
old, new = b'audited synthetic original', b'public source service fixture'
digest = lambda b: hashlib.sha256(b).hexdigest()
mock = r'''#!/usr/bin/env python3
import os,sys,json,shutil,hashlib
from pathlib import Path
name=Path(sys.argv[0]).name;a=sys.argv[1:];base=Path(os.environ['MOCK_ROOT'])
with (base/'calls').open('a') as f:f.write(json.dumps([name]+a)+'\n')
if name==os.environ.get('MOCK_FAIL'):sys.exit(1)
if name in ['toybox','sha256sum']:
 if name=='toybox' and a[:2]==['readlink','-f']:
  print(Path(a[2]).resolve());sys.exit(0)
 if name=='toybox':assert a.pop(0)=='sha256sum'
 kind=os.environ.get('MOCK_HASH','')
 if kind=='empty':sys.exit(0)
 if kind=='error':print('file/tool not ready',file=sys.stderr);sys.exit(1)
 if kind=='invalid':print('abc malformed digest');sys.exit(0)
 try:data=Path(a[0]).read_bytes()
 except OSError as e:print(e,file=sys.stderr);sys.exit(1)
 print(hashlib.sha256(data).hexdigest()+'  '+a[0]);sys.exit(0)
if name=='ls':
 print('u:object_r:'+('sysfs_power' if 'cpufreq_min_limit' in a[-1] else 'hal_power_default_exec')+':s0 '+a[-1]);sys.exit(0)
if name in ['chown','chmod','chcon','sleep']:sys.exit(0)
if name=='setprop':
 assert a==['ctl.restart','vendor.samsung.power-default']
 shutil.copyfile(base/'vendor/bin/hw/android.hardware.power.samsung-service',base/'proc/777/exe')
 sys.exit(0)
if name=='pidof':print('777');sys.exit(0)
if name=='getprop':print('running');sys.exit(0)
if name=='logcat':print('AlicePower: synthetic startup failure');sys.exit(0)
if name=='mount':
 assert a[0]=='--bind';shutil.copyfile(a[2],base/'original');shutil.copyfile(a[1],a[2])
 (base/'mountinfo').write_text('101 1 0:1 /service '+str(Path(a[2]).resolve())+' rw - tmpfs tmpfs rw\n');sys.exit(0)
if name=='umount':
 assert a[0]=='-l'  # Running HAL keeps an executable/mmap reference.
 assert (base/'mountinfo').read_text().startswith('101 '),'must not detach a foreign mount'
 shutil.copyfile(base/'original',a[-1]);(base/'mountinfo').write_text('');sys.exit(0)
if name=='dumpsys':
 if os.environ.get('MOCK_FOREIGN_SWAP')=='1':
  p=base/'mountinfo';p.write_text(p.read_text().replace('101 ','202 ',1))
 running=(base/'proc/777/exe').read_bytes()==(base/'sys/kernel/alice_powerhal').read_bytes()
 if os.environ.get('MOCK_READY')=='1' and (running or os.environ.get('MOCK_READY_OLD_PROCESS')=='1'):
  print('ALICE Power HAL R16 AIDL V2; backend=ready; sessions=16')
 elif running:print('ALICE Power HAL R16 AIDL V2; backend=unavailable; sessions=16')
 sys.exit(0)
raise AssertionError(name)
'''
with tempfile.TemporaryDirectory() as tmp:
    area = Path(tmp)
    bin = area/'bin'
    bin.mkdir()
    for name in ['toybox','sha256sum','ls','chown','chmod','chcon','mount','umount','sleep','setprop','dumpsys','pidof','getprop','logcat']:
        f = bin/name
        f.write_text(mock)
        f.chmod(0o755)

    def fixture(name, target_bytes=old):
        p = area/name
        p.mkdir()
        target = p/'vendor/bin/hw/android.hardware.power.samsung-service'
        blob = p/'sys/kernel/alice_powerhal'
        node = p/'sys/power/alice_power_hint'
        state = p/'data/adb/alice-powerhal'
        rc = p/'vendor/etc/init/power-default-sec.rc'
        manifest = p/'vendor/etc/vintf/manifest/power-samsung.xml'
        for f, data in [(target,target_bytes),(blob,new),(node,b''),
                        (rc,b'service vendor.samsung.power-default /vendor/bin/hw/android.hardware.power.samsung-service'),
                        (manifest,b'<version>2</version>'),(p/'mountinfo',b''),(p/'boot_id',b'current-boot\n'),(p/'proc/777/exe',target_bytes)]:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
        (p/'dev').mkdir()
        s = re.sub(r'^OLD_SHA=.*$', 'OLD_SHA='+digest(old), script, flags=re.M)
        s = re.sub(r'^PATH=.*$', 'PATH='+str(bin)+':'+os.environ['PATH'], s, flags=re.M)
        for prefix in ['/data/adb/alice-powerhal','/vendor/bin/hw/android.hardware.power.samsung-service',
                       '/sys/power/alice_power_hint','/sys/kernel/alice_powerhal',
                       '/vendor/etc/init/power-default-sec.rc','/vendor/etc/vintf/manifest/power-samsung.xml',
                       '/sys/power/cpufreq_min_limit','/dev/alice-powerhal.lock']:
            s = s.replace(prefix, str(p)+prefix)
        s = s.replace('/proc/self/mountinfo',str(p/'mountinfo')).replace('/proc/sys/kernel/random/boot_id',str(p/'boot_id'))
        s=s.replace('/proc/"$pid"/exe',str(p)+'/proc/"$pid"/exe')
        s=s.replace('/system/bin/timeout','/usr/bin/timeout')
        for name in ['toybox','sha256sum','setprop','dumpsys','pidof','getprop','logcat']:
            s = s.replace('/system/bin/'+name,str(bin/name))
        f=p/'boot.sh';f.write_text(s)
        env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],MOCK_ROOT=str(p),MOCK_READY='1')
        return p,target,node,state,f,env

    def run(f, env, action='apply'):
        subprocess.run([test_shell,str(f),action],env=env,check=True,timeout=10)
    def calls(p):
        return [json.loads(l) for l in (p/'calls').read_text().splitlines()]

    # A bind changes the pathname, not the ELF already mapped by init's service.
    p,t,n,s,f,e=fixture('old-process-after-early-bind')
    run(f,e)
    assert t.read_bytes()==new and (p/'proc/777/exe').read_bytes()==old
    run(f,e,'guard')
    assert 'POWERHAL_RUNTIME_READY' in (s/'status.log').read_text(), 'must restart an already running original after early bind'
    assert (p/'proc/777/exe').read_bytes()==new
    run(f,e,'guard')
    assert sum(c[0]=='setprop' for c in calls(p))==1

    p,t,n,s,f,e=fixture('ready')
    run(f,e);assert t.read_bytes()==new and (s/'bound').read_text().startswith('current-boot 101 ')
    (p/'proc/777/exe').write_bytes(new)
    run(f,e,'guard');assert 'POWERHAL_RUNTIME_READY' in (s/'status.log').read_text()
    run(f,e);assert sum(c[0]=='mount' for c in calls(p))==1
    assert not any(c[0]=='setprop' for c in calls(p))

    p,t,n,s,f,e=fixture('vendor-symlink')
    (p/'vendor').rename(p/'real-vendor');(p/'vendor').symlink_to('real-vendor')
    run(f,e,'guard');assert t.read_bytes()==new and 'POWERHAL_RUNTIME_READY' in (s/'status.log').read_text()
    run(f,dict(e,MOCK_READY='0'),'guard');assert t.read_bytes()==old and (s/'auto-disabled').exists()

    for kind in ['empty','error','invalid']:
        p,t,n,s,f,e=fixture('hash-'+kind)
        bad=dict(e,MOCK_HASH=kind)
        run(f,bad,'guard')
        assert t.read_bytes()==old and not (s/'bound').exists() and not (s/'disable').exists()
        assert not any(c[0] in ['mount','umount','dumpsys','setprop'] for c in calls(p))
        assert 'VENDOR_HASH_UNKNOWN' not in (s/'status.log').read_text()
        # Android becomes ready: the finite guard retries the install and restarts through init.
        run(f,e,'guard');assert t.read_bytes()==new
        log=(s/'status.log').read_text()
        assert 'POWERHAL_OWNED_BIND_RESTART' in log and 'POWERHAL_RUNTIME_READY' in log
        assert sum(c[0]=='setprop' for c in calls(p))==1

    p,t,n,s,f,e=fixture('fallback');run(f,e)
    run(f,dict(e,MOCK_READY='0'),'guard')
    assert 'POWERHAL_FALLBACK_VENDOR_RESTORED' in (s/'status.log').read_text()
    assert t.read_bytes()==old and (s/'auto-disabled').exists() and not (s/'disable').exists() and n.read_text()=='reset\n'
    assert sum(c[0]=='dumpsys' for c in calls(p))==9
    assert 'backend=unavailable' in (s/'health-last.log').read_text()
    assert 'AlicePower: synthetic startup failure' in (s/'diagnostic-last.log').read_text()
    before=len(calls(p))
    run(f,e);assert t.read_bytes()==old
    assert not any(c[0] in ['mount','setprop'] for c in calls(p)[before:])

    p,t,n,s,f,e=fixture('late-fallback')
    run(f,dict(e,MOCK_READY='0'),'guard')
    assert t.read_bytes()==old and (s/'auto-disabled').exists()
    assert sum(c[0]=='setprop' for c in calls(p))==2 # start replacement, then restore original

    p,t,n,s,f,e=fixture('misleading-dump')
    run(f,e)
    run(f,dict(e,MOCK_READY_OLD_PROCESS='1'),'guard')
    assert (p/'proc/777/exe').read_bytes()==new
    assert sum(c[0]=='setprop' for c in calls(p))==1

    p,t,n,s,f,e=fixture('restart-request-failure')
    run(f,e)
    run(f,dict(e,MOCK_FAIL='setprop'),'guard')
    assert t.read_bytes()==old and (s/'auto-disabled').exists()
    assert 'RESTART_REQUEST_FAILED' in (s/'status.log').read_text()

    p,t,n,s,f,e=fixture('restart-already-attempted')
    run(f,e)
    (s/'restart-attempt').write_text('current-boot 101 '+digest(new)+'\n')
    run(f,e,'guard')
    assert t.read_bytes()==old and 'POWERHAL_RESTART_ALREADY_REQUESTED' in (s/'status.log').read_text()
    assert sum(c[0]=='setprop' for c in calls(p))==1 # fallback only, no repeated replacement restart

    p,t,n,s,f,e=fixture('manual-or-legacy-disabled')
    s.mkdir(parents=True);(s/'disable').write_text('')
    run(f,e,'guard')
    assert t.read_bytes()==old and (s/'disable').exists()
    assert not any(c[0] in ['mount','umount','setprop','dumpsys','toybox','sha256sum'] for c in calls(p))

    p,t,n,s,f,e=fixture('different-payload-auto-disable')
    s.mkdir(parents=True);(s/'auto-disabled').write_text('ALICE_POWERHAL_R16 '+'0'*64+'\n')
    run(f,e,'guard');assert t.read_bytes()==new

    p,t,n,s,f,e=fixture('unknown',b'unknown');run(f,e,'guard')
    assert 'VENDOR_HASH_UNKNOWN_SKIPPED' in (s/'status.log').read_text() and t.read_bytes()==b'unknown'
    assert not any(c[0] in ['mount','umount','setprop'] for c in calls(p))

    for failure in ['chcon','mount']:
        p,t,n,s,f,e=fixture('fail-'+failure);run(f,dict(e,MOCK_FAIL=failure),'guard')
        assert t.read_bytes()==old and not (s/'bound').exists()
        assert not any(c[0] in ['umount','setprop'] for c in calls(p))

    for foreign_bytes in [old,new]:
        p,t,n,s,f,e=fixture('foreign-'+digest(foreign_bytes)[:6],foreign_bytes)
        (p/'mountinfo').write_text('202 1 0:1 /foreign '+str(t)+' rw - tmpfs tmpfs rw\n')
        run(f,e,'guard')
        assert not any(c[0] in ['mount','umount','setprop'] for c in calls(p))
        assert not (s/'disable').exists() and t.read_bytes()==foreign_bytes

    p,t,n,s,f,e=fixture('stale-boot');run(f,e)
    (p/'boot_id').write_text('next-boot\n')
    run(f,dict(e,MOCK_READY='0'),'guard')
    assert not any(c[0] in ['umount','setprop'] for c in calls(p))

    p,t,n,s,f,e=fixture('swapped-during-health');run(f,e)
    run(f,dict(e,MOCK_READY='0',MOCK_FOREIGN_SWAP='1'),'guard')
    assert 'FALLBACK_UNOWNED_MOUNT_SKIPPED' in (s/'status.log').read_text()
    assert not any(c[0] in ['umount','setprop'] for c in calls(p)) and not (s/'disable').exists()

print('PASS: actual bootstrap rejects empty/error/malformed hashes and retries after readiness')
print('PASS: actual guard requires current-boot owned mount; no rollback of absent, foreign or swapped mounts')
print('PASS: finite late install/restart, busy-mount fallback, unknown ROM and preparation failure behavior')
print('PASS: early bind with old process requires one restart; healthy mapped ELF skips restart; dump alone cannot pass')
print('PASS: startup diagnostic survives rollback; per-payload automatic stop and manual/legacy disable remain separate')
