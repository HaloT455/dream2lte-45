#!/usr/bin/env python3
"""Check the lean package and execute its actual helper against mock sysfs."""
from pathlib import Path
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

app = Path('alice/android-app/app/src/main')
manifest = ET.parse(app/'AndroidManifest.xml').getroot()
assert not manifest.findall('uses-permission')
assert not manifest.findall('.//service') and not manifest.findall('.//receiver')
assert {p.name for p in (app/'java/com/halot455/alice').glob('*.java')} == {'MainActivity.java', 'AliceLruController.java'}
assert {p.name for p in (app/'assets').iterdir()} == {'alice_lru.sh'}
assert not (app/'jniLibs').exists()
core = Path('kernel/alice_sysintel.c').read_text()
assert 'WRITE_ONCE' not in core and 'vm_swappiness' not in core
assert '__ATTR(' not in core and '__ATTR_RO(mm_reclaim)' in core
assert 'model_inference=0' in core and 'manual_vm_policy=0' in core
assert 'IS_ENABLED(CONFIG_LRU_GEN_ENABLED)' in core
assert 'alice_sysintel_reclaim' in core and 'alice_sysintel_no_progress' in core
cfg = Path('arch/arm64/configs/exynos8895-dream2lte_defconfig').read_text()
for setting in ('CONFIG_ALICE_SYSINTEL=y', 'CONFIG_LRU_GEN=y',
                '# CONFIG_LRU_GEN_ENABLED is not set', '# CONFIG_MALI_HALO_NPU_PARTITION is not set',
                'CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYSTEP=y', 'CONFIG_EXYNOS_VPU_HARDWARE=y'):
    assert setting in cfg, setting
source = (app/'assets/alice_lru.sh').read_text()
subprocess.run(['sh', '-n', str(app/'assets/alice_lru.sh')], check=True)

with tempfile.TemporaryDirectory(prefix='alice-lru-r5-') as tmp:
    root = Path(tmp)
    bin = root/'bin'; bin.mkdir()
    m = root/'mglru'; m.write_text('0\n')
    gpu = root/'gpu-boost'; gpu.write_text('-5\n')
    thermal = root/'thermal'; thermal.mkdir()
    zone = thermal/'thermal_zone0'; zone.mkdir()
    (zone/'type').write_text('APOLLO\n'); (zone/'temp').write_text('45000\n')
    battery = root/'battery'; battery.write_text('350\n')
    def executable(name, text):
        p=bin/name; p.write_text('#!/bin/sh\n'+text); p.chmod(0o755)
    executable('id', 'echo "${MOCK_UID:-0}"\n')
    executable('getprop', 'echo "${MOCK_BOOT:-1}"\n')
    executable('sleep', 'test "$1" = 8\n')
    executable('dumpsys', 'echo "MOCK CPU LOAD"\n')
    helper = root/'lru.sh'
    helper.write_text(source.replace('/sys/kernel/mm/lru_gen/enabled', str(m))
                     .replace('/sys/kernel/gpu/gpu_boost', str(gpu))
                     .replace('/sys/class/thermal/thermal_zone', str(thermal/'thermal_zone'))
                     .replace('/sys/class/power_supply/battery/temp', str(battery)))
    env = dict(os.environ, PATH=str(bin)+':'+os.environ['PATH'])
    def run(action, ok=True, extra=None):
        result=subprocess.run(['sh', str(helper), action], env=env|(extra or {}),
                              text=True, capture_output=True, timeout=10)
        assert (result.returncode==0)==ok, (result.returncode, result.stdout, result.stderr)
        return result.stdout
    assert 'mglru=0' in run('status') and m.read_text().strip()=='0'
    assert 'ALICE_GPU_BOOST=-5' in run('gpu-status')
    for value in range(-10,21):
        assert f'ALICE_GPU_BOOST={value}' in run(f'gpu:{value}')
        assert gpu.read_text().strip()==str(value) and m.read_text().strip()=='0'
    for invalid in ('gpu:21','gpu:-11','gpu:bad','gpu:0; echo unexpected','gpu:'):
        run(invalid,False); assert gpu.read_text().strip()=='20'
    run('gpu:0',False,{'MOCK_UID':'2000'});assert gpu.read_text().strip()=='20'
    assert 'ALICE_MGLRU=1' in run('on') and m.read_text().strip()=='1'
    run('trial', False); assert m.read_text().strip()=='1'
    run('off'); assert m.read_text().strip()=='0'
    assert 'ALICE_TRIAL_FINISHED_OFF' in run('trial') and m.read_text().strip()=='0'
    (zone/'temp').write_text('71000\n')
    assert 'ALICE_SOC_HOT_71' in run('on', False) and m.read_text().strip()=='0'
    m.write_text('1\n'); run('off'); assert m.read_text().strip()=='0'
    (zone/'temp').write_text('45000\n'); battery.write_text('427\n')
    assert 'ALICE_BATTERY_HOT' in run('trial', False) and m.read_text().strip()=='0'
    battery.write_text('350\n')
    run('on', False, {'MOCK_BOOT':'0'}); assert m.read_text().strip()=='0'
    run('on', False, {'MOCK_UID':'2000'}); assert m.read_text().strip()=='0'
    run('policy-on', False); assert m.read_text().strip()=='0'
    (zone/'temp').write_text('unavailable\n')
    assert 'ALICE_THERMAL_UNAVAILABLE' in run('on', False)
print('PASS: APK has only manual LRU/GPU activity/controller; no model, native engine, network or service')
print('PASS: kernel bridge exposes read-only counters; native GPU/VPU drivers retained')
print('PASS: real shell helper status, ON/OFF, bounded trial, heat/root/boot gates')
print('PASS: GPU helper verifies applied values; rejects range, injection and non-root writes')
print('NOTE: mock sysfs cannot prove physical MGLRU reclaim stability')
