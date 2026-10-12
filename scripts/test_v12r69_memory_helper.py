#!/usr/bin/env python3
"""Run the bundled root helper against disposable mock ROMs and properties."""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path("alice/android-app/app/src/main/assets/alice_memory.sh").read_text()
names = {
    "aosp": "persist.device_config.lmkd_native.thrashing_limit",
    "samsung": "persist.device_config.slmkd_native.thrashing_limit",
}

with tempfile.TemporaryDirectory(prefix="alice-helper-") as tmp:
    root = Path(tmp)
    bindir = root / "bin"
    bindir.mkdir()
    props = root / "props"
    props.mkdir()
    def executable(name, text):
        p = bindir / name
        p.write_text("#!/bin/sh\n" + text)
        p.chmod(0o755)
    executable("id", 'echo 0\n')
    executable("sleep", ':\n')
    executable("getprop", '''
case "$1" in
 sys.boot_completed) echo 1;;
 init.svc.lmkd) echo running;;
 *) [ ! -f "$TEST_PROPS/$1" ] || cat "$TEST_PROPS/$1";;
esac
''')
    executable("setprop", '''
[ "$TEST_FAIL_RESTORE" != "$2" ] || exit 1
printf '%s' "$2" > "$TEST_PROPS/$1"
''')
    state = root / "data/adb/alice"
    state.mkdir(parents=True)
    for d in ("system/etc/init", "vendor/etc/init", "product/etc/init",
              "system_ext/etc/init", "sys/kernel/mm/lru_gen"):
        (root / d).mkdir(parents=True)
    enabled = root / "sys/kernel/mm/lru_gen/enabled"
    enabled.write_text("0\n")
    # Replace the sandbox paths, preserving the actual shell action code.
    patched = source
    for prefix in ("/data/adb/alice", "/sys/kernel/alice",
                   "/sys/kernel/mm/lru_gen/enabled", "/system/etc/init",
                   "/vendor/etc/init", "/product/etc/init", "/system_ext/etc/init"):
        patched = patched.replace(prefix, str(root) + prefix)
    helper = root / "memory.sh"
    helper.write_text(patched)
    env = dict(os.environ, PATH=str(bindir) + ":" + os.environ["PATH"],
               TEST_PROPS=str(props), TEST_FAIL_RESTORE="never")
    rc = root / "system/etc/init/lmkd.rc"
    def run(*args, success=True, extra=None):
        result = subprocess.run(["sh", str(helper), *args], env=env | (extra or {}),
                                text=True, capture_output=True, timeout=10)
        assert (result.returncode == 0) == success, (args, result.returncode,
                                                    result.stdout, result.stderr)
        return result.stdout
    for kind, prop in names.items():
        rc.write_text(f"on property:{prop}=*\n    setprop lmkd.reinit 1\n"
                      "on property:lmkd.reinit=1\n    exec -- /system/bin/lmkd --reinit\n")
        (props / prop).write_text("77")
        output = run("lmkd-trial", "60")
        assert "ALICE_LMKD_TRIAL_ACTIVE=60" in output
        assert (props / prop).read_text() == "77"
        assert not (state / "lmkd-trial.backup").exists()
        assert not (state / "lmkd-trial.property").exists()
        print(f"PASS: {kind} namespace trial and exact restoration")
    # No matching property trigger: no trial may be applied.
    rc.write_text("on property:lmkd.reinit=1\n")
    assert "ALICE_LMKD_DYNAMIC_UNSUPPORTED" in run("lmkd-trial", "60", success=False)
    assert not (state / "lmkd-trial.backup").exists()
    # Interrupted Samsung backup remains tied to that property after RC changes.
    (state / "lmkd-trial.property").write_text(names["samsung"])
    (state / "lmkd-trial.backup").write_text("77")
    (props / names["samsung"]).write_text("60")
    output = run("restore", success=False, extra={"TEST_FAIL_RESTORE": "77"})
    assert "ALICE_LMKD_RESTORE_FAILED" in output
    assert (state / "lmkd-trial.backup").read_text() == "77"
    run("restore")
    assert (props / names["samsung"]).read_text() == "77"
    # Legacy backup without property metadata still restores AOSP.
    (state / "lmkd-trial.backup").write_text("")
    (props / names["aosp"]).write_text("60")
    run("restore")
    assert (props / names["aosp"]).read_text() == ""
    # An invalid or inaccessible MGLRU target must retain the rollback record.
    (state / "mglru-trial.backup").write_text("0\n")
    enabled.unlink()
    assert "ALICE_MGLRU_RESTORE_FAILED" in run("restore", success=False)
    assert (state / "mglru-trial.backup").exists()
    enabled.write_text("1\n")
    run("restore")
    assert enabled.read_text().strip() == "0"
    assert not (state / "mglru-trial.backup").exists()
    print("PASS: unsupported ROM rejected; interrupted/failed/legacy rollback preserved")
