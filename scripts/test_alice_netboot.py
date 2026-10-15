#!/usr/bin/env python3
"""Compile actual KSU RC, decode its payload, execute its bootstrap and policy.

Android settings and Wi-Fi binder commands are deterministic host fixtures;
these checks cannot establish device boot, RF gain or OEM Wi-Fi behavior.
"""
from pathlib import Path
import base64
import json
import os
import shlex
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
subprocess.run(['python3', str(root/'scripts/gen_alice_netboot.py'), '--check'], check=True)
source = (root/'drivers/kernelsu/runtime/ksud.c').read_text()
decl = source[source.index('static const char KERNEL_SU_RC[]'):source.index('static void stop_vfs_read_hook();')]
script = (root/'alice/netboot/boot.sh').read_bytes()
with tempfile.TemporaryDirectory(prefix='alice-netboot-') as tmp:
    t = Path(tmp)
    c, exe = t/'rc.c', t/'rc'
    c.write_text('#include <stdio.h>\n#define KERNEL_SU_DOMAIN "ksu"\n#define KSUD_PATH "/data/adb/ksud"\n'
                 '#include "drivers/kernelsu/runtime/alice_netboot_payload.h"\n'
                 '#include "drivers/kernelsu/runtime/alice_cpu_compat_payload.h"\n' + decl +
                 '\nint main(void) { fwrite(KERNEL_SU_RC,1,sizeof(KERNEL_SU_RC)-1,stdout); }\n')
    subprocess.run([os.environ.get('HOSTCC','cc'), '-I', str(root), '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
    rc = subprocess.check_output([str(exe)], text=True)
    service = next(l for l in rc.splitlines() if l.startswith('service alice-netboot '))
    argv = shlex.split(service)
    assert argv[:5] == ['service','alice-netboot','/system/bin/sh','-c',argv[-1]]
    command = argv[-1]
    encoded = command.split('printf %s ',1)[1].split(' | ',1)[0]
    assert base64.b64decode(encoded) == script
    assert '$' not in command
    assert '    seclabel u:r:ksu:s0\n' in rc and '    disabled\n    oneshot\n' in rc
    assert 'on property:init.svc.zygote=running\n    start alice-netboot' in rc
    assert 'on property:sys.boot_completed=1\n    start alice-netboot' in rc
    print('PASS: actual KSU RC compiles; init service decodes exact startup script in existing ksu domain')
    bin = t/'bin'; bin.mkdir()
    mock = r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
p=Path(os.environ['TEST_STATE']);d=json.loads(p.read_text());a=sys.argv[1:];name=Path(sys.argv[0]).name
def save():p.write_text(json.dumps(d))
if name=='sleep':d['sleeps']+=1;save();sys.exit(0)
if name=='settings':
 if d.get('unready',0):d['unready']-=1;save();sys.exit(1)
 if a[0]=='get':print(d['dns'].get(a[2],'null'));sys.exit(0)
 d['writes'].append(a)
 if a[0]=='put' and a[2]=='private_dns_mode' and a[3]=='hostname' and d.get('fail_once'):
  d['fail_once']=False;save();sys.exit(1)
 if a[0]=='put':d['dns'][a[2]]=a[3]
 else:d['dns'].pop(a[2],None)
 save();sys.exit(0)
assert name=='cmd' and a[0]=='wifi'
if a[1]=='help':
 if d.get('wifi_unready',0):d['wifi_unready']-=1;save();sys.exit(1)
 print('set-network-selection-config <enabled|disabled> <enabled|disabled> -a <associated_network_selection_override>' if not d.get('unsupported') else 'status')
 sys.exit(0)
assert a[1:]==['set-network-selection-config','enabled','enabled','-a',a[-1]] and a[-1] in ['0','2'],a
d['wifi_requests'].append(a);save()
'''
    for name in ['settings','cmd','sleep']:
        p=bin/name; p.write_text(mock); p.chmod(0o755)
    state=t/'state.json'; area=t/'data'
    env=os.environ|{'PATH':str(bin)+':'+os.environ['PATH'],'TEST_STATE':str(state),'ALICE_NET_STATE':str(area)}
    deployed=area/'boot.sh'
    def reset(dns=None,**extra):
        import shutil
        shutil.rmtree(area,ignore_errors=True)
        state.write_text(json.dumps({'dns':dns or {},'writes':[],'wifi_requests':[],'sleeps':0,'saved_ssid':'user-choice','autojoin':True}|extra))
    def run(action=None):
        if action is None:
            actual=command.replace('/data/adb/alice-netboot',str(area)).replace('/system/bin/','/bin/')
            subprocess.run(['sh','-c',actual],env=env,check=True,timeout=15)
            assert deployed.read_bytes()==script
        else:
            subprocess.run(['sh',str(deployed),action],env=env,check=True,timeout=15)
        d=json.loads(state.read_text()); log=(area/'status.log').read_text()
        assert d['saved_ssid']=='user-choice' and d['autojoin'] is True
        return d,log
    target={'private_dns_mode':'hostname','private_dns_specifier':'dns.adguard-dns.com'}
    reset();d,log=run();assert d['dns']==target and len(d['wifi_requests'])==1 and d['wifi_requests'][0][-1]=='2'
    assert 'dns=1 wifi=1 tries=0' in log
    writes=len(d['writes']);d,log=run();assert len(d['writes'])==writes
    print('PASS: actual embedded bootstrap applies DNS and associated-only Wi-Fi policy; autojoin/SSID untouched; repeat boot idempotent')
    d,log=run('restore');assert not d['dns'] and d['wifi_requests'][-1][-1]=='0' and (area/'disable').exists()
    writes=len(d['writes']);requests=len(d['wifi_requests']);run()
    d=json.loads(state.read_text());assert len(d['writes'])==writes and len(d['wifi_requests'])==requests
    print('PASS: restore deletes originally absent DNS keys, returns Wi-Fi override to platform default and disables future boots')
    old={'private_dns_mode':'hostname','private_dns_specifier':'previous.example'}
    reset(old,fail_once=True);d,log=run();assert d['dns']==target and 'DNS_WRITE_ROLLED_BACK' in log
    d,log=run('restore');assert d['dns']==old
    print('PASS: partial DNS write rollback and original strict-hostname restoration')
    reset(old,unready=100);d,log=run();assert d['dns']==old and not d['writes'] and d['sleeps']==29 and 'dns=0 wifi=1 tries=30' in log
    print('PASS: unavailable SettingsProvider times out after 30 attempts without changes; Wi-Fi applied independently')
    reset(unsupported=True);d,log=run();assert d['dns']==target and not d['wifi_requests'] and 'WIFI_SELECTION_API_UNSUPPORTED' in log
    print('PASS: unsupported OEM Wi-Fi API is reported and skipped without disabling autojoin')
    reset(wifi_unready=2);d,log=run();assert d['sleeps']==2 and len(d['wifi_requests'])==1 and d['dns']==target
    changed={'private_dns_mode':'off','private_dns_specifier':'user.example'}
    d['dns']=changed;state.write_text(json.dumps(d));d,log=run('restore');assert d['dns']==changed and 'DNS_USER_CHANGE_PRESERVED' in log
    print('PASS: late Wi-Fi readiness retried finitely; manual DNS changes survive restore')
