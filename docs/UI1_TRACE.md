# UI1-Trace diagnostic build

Base: `887e9cc5e5678e6c8ee92bd9c8e0edecdaef4856` (UI1).
Branch: `agent/ems-v5-ui1-trace`.

This is an instrumented UI1, not UI2 and not a new performance tune.
The only requested feature is `CONFIG_ENABLE_DEFAULT_TRACERS=y` and its
tracing dependencies. Bluetooth debugfs and F2FS statistics are explicitly
disabled to prevent unrelated defaults from being enabled by DEBUG_FS.
No changes to scheduler/driver/MM source, OPPs, thermal limits, UI hints,
SimpleLMK, KSU, suspend or reboot/recovery handling. CI verifies the effective
configuration delta and rejects changes to those source directories.

Function tracing, dynamic ftrace, latency tracers, syscall tracing and
SCHEDSTATS remain disabled. Event tracing still has memory and runtime costs
when recording; results are diagnostic, not a zero-overhead benchmark.
There is no installed boot service or automatic continuous recorder.

Boot packaging must preserve the matching UI1 ramdisk, DTB, second stage,
header parameters (except kernel size/image ID) and Samsung footer exactly.
Keep the original UI1 boot as rollback. Use the variant you already run;
do not switch to Permissive merely to work around trace access errors.

## Capture (Windows CMD)

The companion APK on `agent/ui-trace-apk` uses this collector for a 60-second
recording without USB; see `apps/ui-trace/README.md`. Both routes remain
on-demand UI diagnostics, not persistent reboot logging.

After flashing the corresponding UI1-Trace boot through your existing
working recovery method, let the phone finish booting and cool down.
Stop/save any other Perfetto, System Tracing or atrace session first.
The collector refuses active event sessions; idle old trace-buffer contents
are replaced by the requested new capture. Keep the USB connection intact
until the command finishes. Do not collect sensitive app content unnecessarily.

```bat
adb push collect_ui_trace.sh /data/local/tmp/collect_ui_trace.sh
adb shell "su -c 'sh /data/local/tmp/collect_ui_trace.sh 60'" > ui1-trace.txt
```

When `Recording` appears, reproduce Home scrolling and the recents transition
for 60 seconds. Upload `ui1-trace.txt`; include stderr if any error appears.
The bundle contains before/after gfxinfo and system snapshots, per-CPU buffer
loss statistics, and the trace delimited by `=== trace begin/end ===`.
It records CPU scheduling, frequency, idle and Binder events plus UI markers;
memory reclaim/disk categories are included only if the ROM exposes them.
Raw timestamps and thread states, not aggregate utilization alone, are needed
to distinguish runnable delay from blocking or UI work.

Only standard tracing controls and, when needed, a temporary tracefs mount
are changed. No SELinux/policy/permission, governor, voltage, thermal, cache,
wakelock or swap writes. The buffer is 8192 KiB per CPU (up to 64 MiB on this
8-core device), kept in RAM and dumped over ADB. The script does not create a
log file on phone storage. This does not assert that the rest of Android makes
no storage writes or that temporary RAM pressure cannot affect the workload.
atrace stops the events and shrinks its buffers on completion; shell traps
also request cleanup on startup failure or interruption. SIGKILL/reboot cannot
be trapped. If cleanup fails, reboot and send the error before testing again.

Do not raise the 65 C threshold or increase boost based only on this build.
Hardware boot, SELinux trace access and on-device capture still require testing.
