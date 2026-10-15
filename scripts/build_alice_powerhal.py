#!/usr/bin/env python3
"""Build a VINTF AIDL V2 Power HAL using only public Android sources/tools.

libbinder_ndk platform service APIs are not in the app NDK link stub. A link-only
stub supplements the NDK's symbol list with four exported platform APIs. It is
NEVER installed or embedded; the ELF uses the ROM's real libbinder_ndk.so.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import subprocess
import urllib.request

root = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('--ndk', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
p.add_argument('--tools', required=True, type=Path)
args = p.parse_args()
ndk, out, tools = args.ndk.resolve(), args.out.resolve(), args.tools.resolve()
out.mkdir(parents=True, exist_ok=True)
tools.mkdir(parents=True, exist_ok=True)
revision = '7f3afbad863222c9e3a5a04ef7efb3d6ab7235ca'
hashes = {'aidl': '5363550e125768416de18fc521f1c4aede4a5eca0e243cd5744458e1f8010e96',
          'libc++.so': '35c380b65a849438d3bebcd87acc920d6df6d5cd003c21c903545aaba945441b'}
for name, digest in hashes.items():
    file = tools/name
    if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
        directory = 'bin' if name == 'aidl' else 'lib64'
        url = f'https://android.googlesource.com/platform/prebuilts/build-tools/+/{revision}/linux-x86/{directory}/{name}?format=TEXT'
        with urllib.request.urlopen(url, timeout=60) as response:
            data = base64.b64decode(response.read())
        assert hashlib.sha256(data).hexdigest() == digest, name
        file.write_bytes(data)
    if name == 'aidl': file.chmod(0o755)
llvm = ndk/'toolchains/llvm/prebuilt/linux-x86_64'
cc, cxx = llvm/'bin/aarch64-linux-android33-clang', llvm/'bin/aarch64-linux-android33-clang++'
assert '27.3.13750724' in (ndk/'source.properties').read_text(), 'use Android NDK r27d'
include, src = out/'include', out/'src'
include.mkdir(exist_ok=True)
src.mkdir(exist_ok=True)
api = root/'alice/powerhal/aidl'
env = dict(os.environ, LD_LIBRARY_PATH=str(tools))
subprocess.run([str(tools/'aidl'), '--lang=ndk', '--structured', '--stability=vintf',
                '--min_sdk_version=33', '--version=2', '--hash=ef4f5ed58e39693f25c1f8fdcfe7b958c6b800bc',
                '-I'+str(api), '-o', str(src), '-h', str(include),
                *map(str, sorted(api.rglob('*.aidl')))], env=env, check=True)
symbols = set()
stub = llvm/'sysroot/usr/lib/aarch64-linux-android/33/libbinder_ndk.so'
for line in subprocess.check_output(['readelf', '-Ws', str(stub)], text=True).splitlines():
    f = line.split()
    if len(f) >= 8 and f[3] == 'FUNC' and f[4] == 'GLOBAL' and f[6] != 'UND':
        symbols.add(f[7].split('@')[0])
symbols.update(['AServiceManager_addService', 'ABinderProcess_setThreadPoolMaxThreadCount',
                'ABinderProcess_joinThreadPool', 'AIBinder_markVintfStability'])
link_c = out/'link-only-stub.c'
link_c.write_text('\n'.join('void '+s+'(void) {}' for s in sorted(symbols))+'\n')
subprocess.run([str(cc), '-shared', '-Wl,-soname,libbinder_ndk.so', str(link_c),
                '-o', str(out/'libbinder_ndk.so')], check=True)
elf = out/'android.hardware.power.samsung-service'
subprocess.run([str(cxx), '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O2', '-fPIE',
                '-fvisibility=hidden', '-ffunction-sections', '-fdata-sections', '-static-libstdc++',
                '-DBINDER_STABILITY_SUPPORT', '-Wl,--gc-sections,-z,relro,-z,now',
                '-I'+str(include), '-I'+str(root/'alice/powerhal/platform'),
                str(root/'alice/powerhal/Power.cpp'), *map(str, sorted(src.rglob('*.cpp'))),
                '-L'+str(out), '-lbinder_ndk', '-llog', '-o', str(elf)], check=True)
subprocess.run([str(llvm/'bin/llvm-strip'), '--strip-unneeded', str(elf)], check=True)
dynamic = subprocess.check_output(['readelf', '-d', str(elf)], text=True)
assert 'libbinder_ndk.so' in dynamic and 'libc++_shared.so' not in dynamic
assert str(out) not in dynamic, 'no build path RPATH'
subprocess.run(['python3', str(root/'scripts/gen_alice_powerhal.py'), '--check', '--elf', str(elf)], check=True)
metadata = {'aidl_version': 2, 'aidl_hash': 'ef4f5ed58e39693f25c1f8fdcfe7b958c6b800bc',
            'ndk': '27.3.13750724', 'sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
            'bytes': elf.stat().st_size, 'dynamic': dynamic, 'link_stub_shipped': False}
(out/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
print(json.dumps({k: v for k, v in metadata.items() if k != 'dynamic'}, indent=2))
