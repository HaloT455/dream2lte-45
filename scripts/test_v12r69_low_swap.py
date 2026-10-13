#!/usr/bin/env python3
"""Test Samsung swap-reference correction and actual repair script transactions.

Arithmetic follows supplied LMKD ARM64 code at a9c8/18078/1825c. Mock properties
and reinit test the script; no LMKD process or Android kernel runs on this host.
"""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path("scripts/alice-v12r69-low-swap.sh").read_text()
# This optional standalone repair is deliberately excluded from the LRU-only APK.

def samsung_effective(nominal, reference_kb, actual_swap_kb):
    used_limit = int((100-nominal)/100 * reference_kb)
    return max(1, min(100, int((1-used_limit/actual_swap_kb+0.001)*100)))

assert samsung_effective(72, 2621440, 3355440) == 78
assert samsung_effective(10, 2621440, 3355440) == 29
for actual in (3000000, 3355440, 4199996, 4200000):
    base_mb = (actual+1023)//1024
    for nominal in (1, 10, 20, 30):
        assert samsung_effective(nominal, base_mb*1024, actual) == nominal

with tempfile.TemporaryDirectory(prefix="low-swap-") as tmp:
    root = Path(tmp)
    bindir = root/"bin"; bindir.mkdir()
    props = root/"props"; props.mkdir()
    state = root/"state"; state.mkdir()
    meminfo=root/"meminfo"; meminfo.write_text("MemAvailable: 726288 kB\nSwapTotal: 3355440 kB\nSwapFree: 2563924 kB\n")
    swaps=root/"swaps"; swaps.write_text("Filename Type Size Used Priority\n/dev/block/zram0 partition 3355440 791516 -1\n")
    boot=root/"boot-id"; boot.write_text("boot-one\n")
    def executable(name, body):
        p=bindir/name; p.write_text("#!/bin/sh\n"+body); p.chmod(0o755)
    executable("id", "echo 0\n")
    executable("sleep", ":\n")
    executable("timeout", 'shift\n"$@"\n')
    executable("getprop", '''
case "$1" in
 sys.boot_completed) echo 1;;
 init.svc.lmkd) echo running;;
 *) [ ! -f "$TEST_PROPS/$1" ] || cat "$TEST_PROPS/$1";;
esac
''')
    executable("resetprop", '''
[ "$1" = -n ] || exit 1
[ "$TEST_RESET_FAIL" != "$3" ] || exit 1
printf '%s' "$3" > "$TEST_PROPS/$2"
''')
    daemon=bindir/"lmkd"
    daemon.write_text('''#!/usr/bin/env python3
import os,pathlib
if os.environ.get('TEST_REINIT_FAIL')=='1':raise SystemExit(1)
p=pathlib.Path(os.environ['TEST_PROPS'])
def get(k,default):
 f=p/k
 return int(f.read_text()) if f.exists() and f.read_text().strip() else default
base=get('ro.slmk.base_swaptotal',2560)*1024
nominal=get('ro.slmk.swap_free_low_percentage',72)
nominal=get('ro.slmk.2nd.swap_free_low_percentage',nominal)
nominal=get('persist.device_config.lmkd_native.swap_free_low_percentage',nominal)
effective=max(1,min(100,int((1-int((100-nominal)/100*base)/3355440+0.001)*100)))
if os.environ.get('TEST_STALE')=='1':effective=78
(p/'sys.lmk.slmk_16up_swap_free_low_percentage').write_text(str(effective))
'''); daemon.chmod(0o755)
    import hashlib
    digest=hashlib.sha256(daemon.read_bytes()).hexdigest()
    helper=root/"repair.sh"
    helper.write_text(source.replace("/data/adb/alice",str(state))
                     .replace("/system/bin/lmkd",str(daemon))
                     .replace("/proc/meminfo",str(meminfo))
                     .replace("/proc/swaps",str(swaps))
                     .replace("/proc/sys/kernel/random/boot_id",str(boot))
                     .replace("3bbca06f1f7dcc1be36b7e16d70e6ffe833fe420bab7a380b8582e3f3a822b49",digest))
    env=dict(os.environ,PATH=str(bindir)+":"+os.environ["PATH"],TEST_PROPS=str(props),TEST_RESET_FAIL="never")
    def setprop(k,v): (props/k).write_text(v)
    def getprop(k):
        p=props/k
        return p.read_text().strip() if p.exists() else ""
    def run(action, success=True, extra=None):
        p=subprocess.run(["sh",str(helper),action],env=env|(extra or {}),text=True,capture_output=True,timeout=10)
        assert (p.returncode==0)==success,(p.returncode,p.stdout,p.stderr)
        return p.stdout
    setprop("ro.slmk.swap_free_low_percentage","72")
    setprop("ro.slmk.2nd.swap_free_low_percentage","72")
    setprop("sys.lmk.slmk_16up_swap_free_low_percentage","78")
    assert "effective=10" in run("apply")
    assert getprop("ro.slmk.base_swaptotal")=="3277"
    run("restore")
    assert getprop("ro.slmk.base_swaptotal")==""
    assert getprop("ro.slmk.swap_free_low_percentage")=="72"
    assert getprop("ro.slmk.2nd.swap_free_low_percentage")=="72"
    assert getprop("sys.lmk.slmk_16up_swap_free_low_percentage")=="78"
    # Respect a supported explicit override, rather than overwriting it.
    setprop("persist.device_config.lmkd_native.swap_free_low_percentage","20")
    assert "effective=20" in run("apply")
    run("restore")
    assert getprop("persist.device_config.lmkd_native.swap_free_low_percentage")=="20"
    setprop("persist.device_config.lmkd_native.swap_free_low_percentage","72")
    assert "EXISTING_OVERRIDE_REQUIRES_REVIEW" in run("apply",success=False)
    setprop("persist.device_config.lmkd_native.swap_free_low_percentage","")
    # Unconfirmed state and partial write are rolled back.
    assert "NOT_CONFIRMED" in run("apply",success=False,extra={"TEST_STALE":"1"})
    assert getprop("ro.slmk.swap_free_low_percentage")=="72"
    run("apply",success=False,extra={"TEST_RESET_FAIL":"10"})
    assert getprop("ro.slmk.base_swaptotal")==""
    assert not (state/"low-swap.backup").exists()
    # Failed reinit retains the backup for a subsequent restore.
    run("apply",success=False,extra={"TEST_REINIT_FAIL":"1"})
    assert (state/"low-swap.backup").exists()
    run("restore")
    # Do not overwrite a property independently modified after applying.
    run("apply"); setprop("ro.slmk.base_swaptotal","4000")
    run("restore",success=False)
    assert getprop("ro.slmk.base_swaptotal")=="4000"
    setprop("ro.slmk.base_swaptotal","3277"); run("restore")
    # KernelSU's bundled ksud backend also works when no standalone resetprop exists.
    (bindir/"resetprop").rename(bindir/"resetprop.saved")
    executable("ksud", '''
[ "$1" = resetprop ] || exit 1
shift
if [ "$1" = ro.build.version.sdk ]; then echo 36; exit 0; fi
"$(dirname "$0")/resetprop.saved" "$@"
''')
    assert "effective=10" in run("apply")
    run("restore")
    (bindir/"resetprop.saved").rename(bindir/"resetprop")
    # A different daemon is rejected before any property changes.
    daemon.write_text(daemon.read_text()+"\n# changed\n")
    assert "BINARY_MISMATCH" in run("apply",success=False)
    assert getprop("ro.slmk.swap_free_low_percentage")=="72"
    assert not (state/"memory-experiment.lock").exists()
print("PASS: Samsung 72->78 transform and swap-reference normalization")
print("PASS: apply/verify/restore, override preservation, mismatch and failure rollback")
