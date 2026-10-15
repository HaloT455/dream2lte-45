#!/usr/bin/env python3
"""Exercise actual embedded CPU setup with synthetic Android files/commands.

Real bind mount, init ordering and SELinux behavior still require device checks.
The full private ROM profile and user logs are never part of this fixture.
"""
from pathlib import Path
import base64
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile

root=Path(__file__).resolve().parent.parent
test_shell=os.environ.get('ALICE_TEST_SHELL','sh')
print('Bootstrap test shell:', test_shell, flush=True)
subprocess.run(['python3',str(root/'scripts/gen_alice_cpu_compat.py'),'--check'],check=True)
script=(root/'alice/cpu-compat/boot.sh').read_text()
ksu=(root/'drivers/kernelsu/runtime/ksud.c').read_text()
decl=ksu[ksu.index('static const char KERNEL_SU_RC[]'):ksu.index('static void stop_vfs_read_hook();')]
sha=lambda s:hashlib.sha256(s.encode()).hexdigest()
fixture={
 'Attributes':[{'Name':'GpisSfCpuset','Controller':'cpuset','File':'cpus'}],
 'Profiles':[
  {'Name':'GpisSfCpusetJoin','Actions':[{'Name':'JoinCgroup','Params':{'Controller':'cpuset','Path':'sf'}}]},
  *[{'Name':'GpisSfCpuset'+name,'Actions':[{'Name':'SetAttribute','Params':{'Name':'GpisSfCpuset','Value':val}}]}
    for name,val in [('Enable','4-7'),('Disable','0-7')]],
  {'Name':'Unrelated','Actions':[{'Name':'SetAttribute','Params':{'Name':'Other','Value':'unchanged'}}]}],
 'AggregateProfiles':[{'Name':'GPIS_HINT_ENABLE','Profiles':['GpisSfCpusetEnable']}]}
original=json.dumps(fixture,indent=2)+'\n'
fixed=json.loads(original)
for p in fixed['Profiles']:
 if p['Name'] in ['GpisSfCpusetEnable','GpisSfCpusetDisable']:
  p['Actions'][0]['Name']='WriteFile'
  p['Actions'][0]['Params']['FilePath']='/dev/cpuset/sf/cpus'
  del p['Actions'][0]['Params']['Name']
# Keep parameter order matching awk's in-place key substitution.
fixed_text=original.replace('"Name": "SetAttribute",\n', '"Name": "SetAttribute",\n')
for name in ['GpisSfCpusetEnable','GpisSfCpusetDisable']:
 a=fixed_text.index('"Name": "'+name+'"');b=fixed_text.index('"Value"',a)
 chunk=fixed_text[a:b].replace('"Name": "SetAttribute"','"Name": "WriteFile"').replace(
  '"Name": "GpisSfCpuset"','"FilePath": "/dev/cpuset/sf/cpus"')
 fixed_text=fixed_text[:a]+chunk+fixed_text[b:]
assert json.loads(fixed_text)==fixed

with tempfile.TemporaryDirectory(prefix='alice-cpu-compat-') as tmp:
 t=Path(tmp);c=t/'rc.c';exe=t/'rc'
 c.write_text('#include <stdio.h>\n#define KERNEL_SU_DOMAIN "ksu"\n#define KSUD_PATH "/data/adb/ksud"\n'
 '#include "drivers/kernelsu/runtime/alice_netboot_payload.h"\n'
 '#include "drivers/kernelsu/runtime/alice_cpu_compat_payload.h"\n'
                 '#include "drivers/kernelsu/runtime/alice_powerhal_payload.h"\n'+decl+
 '\nint main(void){fwrite(KERNEL_SU_RC,1,sizeof(KERNEL_SU_RC)-1,stdout);}\n')
 subprocess.run([os.environ.get('HOSTCC','cc'),'-I',str(root),'-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
 rc=subprocess.check_output([str(exe)],text=True)
 block=rc.split('# ALICE_CPU_COMPAT_R15\n',1)[1]
 assert block.startswith('on post-fs-data\n    exec ')
 line=block.splitlines()[1];args=shlex.split(line)
 assert args[:10]==['exec','u:r:ksu:s0','root','root','--','/system/bin/timeout','8','/system/bin/sh','-c',args[-1]]
 payload=args[-1].split('printf %s ',1)[1].split(' | ',1)[0]
 assert base64.b64decode(payload).decode()==script and '$' not in args[-1]
 assert 'on property:init.svc.surfaceflinger=running\n    exec u:r:ksu:s0 root root -- /system/bin/timeout 5' in block
 print('PASS: actual linked KSU RC embeds exact bounded post-fs-data script and SurfaceFlinger restart trigger')
 area=t/'android';bin=t/'bin';bin.mkdir();state=area/'data/adb/alice-cpu-compat'
 target=area/'system/etc/task_profiles.json';group=area/'dev/cpuset/sf'
 # Substitute only external paths and fixture hashes; patching/control flow is actual source.
 test_script=script.replace('PATH=/system/bin:/system/xbin:/vendor/bin:/vendor/xbin:/sbin','PATH='+str(bin)+':'+os.environ['PATH']).replace('TOYBOX=/system/bin/toybox','TOYBOX='+str(bin/'toybox')).replace('/system/bin/sha256sum',str(bin/'sha256sum')).replace('/dev/alice-cpu-compat.ready',str(area/'dev/alice-cpu-compat.ready'))
 test_script=re.sub(r'^OLD_SHA=.*$', 'OLD_SHA='+sha(original),test_script,flags=re.M)
 test_script=re.sub(r'^NEW_SHA=.*$', 'NEW_SHA='+sha(fixed_text),test_script,flags=re.M)
 for path in ['/data/adb/alice-cpu-compat','/system/etc/task_profiles.json','/dev/cpuset','/proc/']:
  # Keep JSON WriteFile literals unmodified so output remains production-valid.
  if path=='/dev/cpuset':
   test_script=test_script.replace('GROUP=/dev/cpuset/sf','GROUP='+str(group)).replace('cat /dev/cpuset/','cat '+str(area/'dev/cpuset')+'/')
  else:test_script=test_script.replace(path,str(area)+path)
 device=t/'device.sh';device.write_text(test_script)
 mock=r'''#!/usr/bin/env python3
import os,sys,json,subprocess,shutil,hashlib
from pathlib import Path
name=Path(sys.argv[0]).name;a=sys.argv[1:];base=Path(os.environ['MOCK_ROOT']);log=Path(os.environ['MOCK_CALLS'])
with log.open('a') as f:f.write(json.dumps([name]+a)+'\n')
fail=os.environ.get('MOCK_FAIL','')
if name==fail:sys.exit(1)
if name in ['toybox','sha256sum']:
 mode=os.environ.get('MOCK_HASH_MODE','')
 if mode=='error':sys.exit(1)
 if mode=='empty':sys.exit(0)
 if mode=='malformed':print('not_a_digest');sys.exit(0)
 if mode=='failed_digest':print('0'*64+'  '+a[-1]);sys.exit(1)
 try: digest=hashlib.sha256(Path(a[-1]).read_bytes()).hexdigest()
 except OSError:sys.exit(1)
 print(digest+'  '+a[-1]);sys.exit(0)
if name=='mkdir':
 rc=subprocess.run(['/bin/mkdir']+a).returncode
 if not rc and a[-1]==str(base/'dev/cpuset/sf'):
  for n in ['cpus','mems','tasks','cgroup.procs']:(Path(a[-1])/n).touch()
 sys.exit(rc)
if name in ['chmod','chown','chcon']:sys.exit(0)
if name=='ls':print('u:object_r:system_cgroup_desc_file:s0 '+a[-1]);sys.exit(0)
if name=='mount':
 assert a[0]=='--bind'
 shutil.copyfile(a[1],a[2]);sys.exit(0)
if name=='pidof':print('4242');sys.exit(0)
if name=='umount':sys.exit(0)
raise AssertionError(name)
'''
 for name in ['mkdir','chmod','chown','chcon','mount','umount','pidof','ls','toybox','sha256sum']:
  p=bin/name;p.write_text(mock);p.chmod(0o755)
 calls=t/'calls.jsonl'
 env=os.environ|{'PATH':str(bin)+':'+os.environ['PATH'],'MOCK_ROOT':str(area),'MOCK_CALLS':str(calls)}
 def reset(content=original,mask='0-7\n'):
  import shutil
  shutil.rmtree(area,ignore_errors=True);calls.write_text('')
  target.parent.mkdir(parents=True);target.write_text(content)
  cpuset=area/'dev/cpuset';cpuset.mkdir(parents=True)
  (cpuset/'cpus').write_text(mask);(cpuset/'mems').write_text('0\n')
  proc=area/'proc/4242';proc.mkdir(parents=True)
  (proc/'comm').write_text('surfaceflinger\n');(proc/'status').write_text('Uid:\t1000\t1000\t1000\t1000\nCpus_allowed_list:\t0-7\n')
  (proc/'cgroup').write_text('2:cpuset:/\n')
 def run(action='apply',fail='',hash_mode=''):
  subprocess.run([test_shell,str(device),action],env=env|{'MOCK_FAIL':fail,'MOCK_HASH_MODE':hash_mode},check=True,timeout=5)
  return [json.loads(x) for x in calls.read_text().splitlines()],(state/'status.log').read_text()
 reset();ops,log=run()
 assert target.read_text()==fixed_text
 assert (area/'dev/cpuset/cpus').read_text()=='0-7\n'
 assert (group/'cpus').read_text()=='0-7\n' and (group/'mems').read_text()=='0\n'
 assert (group/'cgroup.procs').read_text()=='4242\n'
 assert 'PROFILE_BOUND_GPIS_SF_ONLY' in log and 'SF_PROCESS_JOIN_REQUESTED' in log
 assert len([x for x in ops if x[0]=='mount'])==1
 ops,log=run();assert len([x for x in ops if x[0]=='mount'])==1 and 'PROFILE_ALREADY_FIXED' in log
 run('join');assert target.read_text()==fixed_text
 print('PASS: two GPIS actions use only absolute sf/cpus; group created/joined; root mask and unrelated profiles unchanged; repeated boot does not stack mounts')
 reset(original+'\n');ops,log=run();assert 'PROFILE_HASH_UNRECOGNIZED_SKIPPED' in log
 assert group.exists() and (group/'cgroup.procs').read_text()=='4242\n' and not any(x[0]=='mount' for x in ops)
 assert (area/'dev/cpuset/cpus').read_text()=='0-7\n'
 print('PASS: unknown JSON remains untouched; root-only SF can join its 0-7 group without depending on profile binding')
 reset();state.mkdir(parents=True);(state/'disable').touch();ops,log=run()
 assert target.read_text()==original and not group.exists() and 'DISABLED' in log
 reset(mask='0-3\n');ops,log=run();assert target.read_text()==original and not group.exists()
 print('PASS: disable marker and CPU-layout guard preserve original configuration')
 for failure in ['chcon','mount']:
  reset();ops,log=run(fail=failure);assert target.read_text()==original
  assert 'PROFILE_BOUND_GPIS_SF_ONLY' not in log
 print('PASS: label/bind failure leaves original task profile in place')

 for mode in ['error','empty','malformed','failed_digest']:
  reset();ops,log=run(hash_mode=mode)
  assert target.read_text()==original and not any(x[0]=='mount' for x in ops)
  assert (group/'cgroup.procs').read_text()=='4242\n'
  assert 'PROFILE_READ_UNAVAILABLE_DEFERRED' in log
 print('PASS: unreadable, empty, malformed and failed-exit digest do not authorize a JSON edit; SF group remains usable')
 reset();group.mkdir()
 for n,v in [('cpus','0-7\n'),('mems','0\n'),('tasks',''),('cgroup.procs','')]: (group/n).write_text(v)
 ops,log=run();assert 'SF_FOREIGN_GROUP_SKIPPED' in log and target.read_text()==original
 print('PASS: existing foreign group is never taken over')
 for cgroup,mask,uid in [('/foreground','0-7','1000'),('/','0-3','1000'),('/','0-7','1001')]:
  reset();proc=area/'proc/4242'
  (proc/'cgroup').write_text('2:cpuset:'+cgroup+'\n')
  (proc/'status').write_text('Uid:\t'+uid+'\nCpus_allowed_list:\t'+mask+'\n')
  run();assert (group/'cgroup.procs').read_text()==''
 print('PASS: explicit ROM placement, task affinity and UID are preserved')
