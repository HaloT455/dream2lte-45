#!/usr/bin/env python3
"""Exercise the shipped APK's recording/stop/export UI on a non-root API36 emulator."""
import csv
import io
import re
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

PKG = 'com.halot455.alice.diaglite'
COMPONENT = PKG + '/com.halot455.alice.diag.MainActivity'
def adb(*args):
    result = subprocess.run(['adb', *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    if result.returncode:
        print('ADB failed:', args, result.returncode, result.stdout, flush=True)
        Path('smoke-output').mkdir(exist_ok=True)
        errors = subprocess.run(['adb', 'logcat', '-d', '-s', 'AndroidRuntime:E', 'ActivityTaskManager:E'], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15).stdout
        print(errors, flush=True)
        Path('smoke-output/failure-logcat.txt').write_text(errors)
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout)
    return result.stdout
def tap(label):
    for attempt in range(7):
        adb('shell', 'uiautomator', 'dump', '/sdcard/alice-window.xml')
        tree = ET.fromstring(adb('shell', 'cat', '/sdcard/alice-window.xml'))
        for node in tree.iter('node'):
            if node.attrib.get('text') == label:
                coords = list(map(int, re.findall(r'\d+', node.attrib['bounds'])))
                x1, y1, x2, y2 = coords
                if y2 > y1 and x2 > x1:
                    adb('shell', 'input', 'tap', str((x1 + x2) // 2), str((y1 + y2) // 2))
                    return
        adb('shell', 'input', 'swipe', '500', '1500', '500', '500', '300')
        time.sleep(.5)
    Path('smoke-output').mkdir(exist_ok=True)
    Path('smoke-output/failure-window.xml').write_text(ET.tostring(tree, encoding='unicode'))
    print('Visible UI:', [(n.attrib.get('text'), n.attrib.get('package')) for n in tree.iter('node') if n.attrib.get('text')])
    print(adb('logcat', '-d', '-s', 'AndroidRuntime:E'))
    raise AssertionError(f'Button not found: {label}')

adb('shell', 'pm', 'grant', PKG, 'android.permission.POST_NOTIFICATIONS')
adb('shell', 'appops', 'set', PKG, 'GET_USAGE_STATS', 'allow')
launch_output = adb('shell', 'am', 'start', '-W', '-n', COMPONENT)
print(launch_output)
assert 'Error' not in launch_output, launch_output
time.sleep(2)
tap('Bắt đầu ghi')
time.sleep(8)
services = adb('shell', 'dumpsys', 'activity', 'services', PKG)
assert 'isForeground=true' in services, services
adb('shell', 'am', 'start', '-a', 'android.settings.SETTINGS')
time.sleep(2)
# Returning to the visible activity and using its stop action also verifies intent routing.
launch_output = adb('shell', 'am', 'start', '-W', '-n', COMPONENT)
print(launch_output)
assert 'Error' not in launch_output, launch_output
tap('Dừng ghi')
time.sleep(3)
services = adb('shell', 'dumpsys', 'activity', 'services', PKG)
assert 'isForeground=true' not in services, services
tap('Xuất ZIP log')
time.sleep(3)
listing = adb('shell', 'ls', '/sdcard/Download/').splitlines()
exports = [name for name in listing if name.startswith('ALICE-DIAG-') and name.endswith('.zip')]
assert exports, listing
Path('smoke-output').mkdir(exist_ok=True)
adb('pull', '/sdcard/Download/' + exports[-1], 'smoke-output/log.zip')
with zipfile.ZipFile('smoke-output/log.zip') as archive:
    assert archive.testzip() is None
    rows = list(csv.DictReader(io.StringIO(archive.read('battery.csv').decode())))
    assert rows and rows[0]['root_state'] == 'unavailable', rows
    assert 'Chưa đủ' in archive.read('SUMMARY.txt').decode()
    assert 'com.android.settings' in archive.read('usage-events.csv').decode(), archive.read('usage-events.csv')
    assert not any('logcat' in name for name in archive.namelist())
# There must be no receiver that automatically starts the recorder on reboot.
package = adb('shell', 'dumpsys', 'package', PKG)
assert 'BOOT_COMPLETED' not in package
# Exercise the exact periodic asset on Android's shell; keep timing separate from
# the APK non-root test. This is not a Samsung/KSU or battery-life measurement.
import json
asset = 'tools/AliceDiag/app/src/main/assets/sample.sh'
adb('push', asset, '/data/local/tmp/alice-diag-sample.sh')
timings = []
for _ in range(5):
    start = time.monotonic()
    output = adb('shell', 'detail=0 /system/bin/sh /data/local/tmp/alice-diag-sample.sh')
    timings.append(round((time.monotonic() - start) * 1000, 2))
    assert '@@ /proc/stat' in output
Path('smoke-output/sampler-benchmark.json').write_text(json.dumps({'environment':'Android36 emulator adb shell; not Samsung/KSU', 'fast_sample_adb_wall_ms':timings},indent=2))
assert max(timings) < 3000, timings
log = adb('logcat', '-d', '-s', 'AndroidRuntime:E')
assert 'FATAL EXCEPTION' not in log, log
print('Sampler shell timings (emulator adb wall ms):', timings)
print('PASS: launch -> foreground recording without root + optional usage access -> stop -> Downloads ZIP; no boot restart')
