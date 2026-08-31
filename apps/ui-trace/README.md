# ALice UI Trace 1.1

Native Java root APK, one user-initiated **60-second** UI trace.
Android 8+ API compatibility; the ROM must also provide a working **Perfetto**
command and system traced/traced_probes services. Compile/target SDK 35.
The UI1-Trace kernel (or equivalent event tracing support) is still required.

## Why the recorder changed

The user's 1.0 capture overwrote 2,765,932 kernel events, hit the 128M-character
text cap and timed out during export. Only about 8.81 seconds were common to
all CPUs in the retained data. Enlarging that rolling RAM buffer alone would
not fix the pipeline.

1.1 uses native Perfetto, continuously draining binary ftrace data. Java reads
only metadata/status, never millions of formatted event lines. The trace is
written to phone storage while measuring: this has I/O and tracing overhead.
It is not a zero-overhead benchmark and cannot guarantee zero dropped events.

The fixed config requests 60,000 ms, 2 MiB ftrace buffers per CPU, an 18 MiB
central buffer, 100 ms ftrace drain and 1-second file writes. The binary file
has a 256 MiB cap. Perfetto stops early if that cap is reached; this is flagged
as incomplete, not silently described as a complete minute. Native Perfetto
statistics inside the trace must be checked during analysis for data loss.

## Install and record

Export old logs before uninstalling 1.0. CI uses a fresh diagnostic signing
key, so 1.1 normally needs uninstall/reinstall (same package ID). Uninstalling
or clearing app data removes private logs.

1. Keep the matching UI1-Trace boot and SELinux variant already in use.
2. Reboot if the previous recorder timed out, then let the phone cool down.
3. Install 1.1; open **Cấp root / kiểm tra kernel**, approve KernelSU root.
4. Ensure at least 600 MiB free, and stop/save other tracing sessions first.
5. Tap **Ghi log 60 giây**, then reproduce the stutter. USB is unnecessary.
6. Return when finished and share the **ZIP**. Its TXT is metadata, not the full
   timeline. If no ZIP was created, share the error TXT instead.

ZIP contains `capture.perfetto-trace`, `metadata.txt`, and `config.pbtxt`.
The binary can be opened in https://ui.perfetto.dev after extraction.
A level-1 ZIP is produced only after tracing has ended, with bounded streaming
memory. A partially-written ZIP is never advertised as complete. Completed
bundles and TXT logs are not automatically deleted or uploaded.

## Limits and safety

No INTERNET, storage-management, accessibility, installation, wake-lock or
boot receiver permission. No arbitrary root-command UI. No persistent service,
root installation, SELinux weakening, chmod, system remount, thermal/frequency/
swap/cache tuning or automatic Perfetto-service enabling.

Root commands check UID/kernel/Perfetto, execute the fixed packaged collector,
or send TERM to its exact owned script PID (full argv match, not substring).
The collector similarly signals only its own Perfetto child, never pkill,
killall, another tracing session or the shared traced daemon. It refuses
already-active events/atrace properties. Other tracers must remain stopped
while this capture runs; the preflight is not an atomic lock against them.

If needed, a standard temporary tracefs mount is attempted. A ROM's mount
namespace or SELinux policy may prevent system traced_probes using it. This
is a compatibility error to report, not a reason to change SELinux or restart
system services. Missing required scheduler/reclaim events fail the capture.

Cancellation requests flush/stop of the owned session. A 150-second root-phase
watchdog requests cancellation, then terminates an unresponsive su client
15 seconds later. Stopping su is not proof its root child stopped. SIGKILL,
process death and reboot cannot guarantee cleanup. On an unconfirmed cleanup,
the app preserves diagnostics and advises reboot before recording again.
Partial raw files can remain private after a failure; successfully archived
raw/config/script intermediates are removed. No recovery of kernel panic logs
across reboot is promised.

Logs contain app/process names, UI markers, memory and diagnostic metadata.
Only share with intended recipients. No heap dump, screenshot or logcat data
source is configured. On-device ROM permissions, full 60-second loss checks,
UI/sharing and cancellation still need hardware verification.

## Build and tests

Build: `bash apps/ui-trace/build.sh` with JDK 17, Android platform 35 and
build-tools 35.0.0. CI runs fake-filesystem collector success/failure/cancellation
tests, exact path/PID validation, and a 144 MiB ZIP round trip with a 32 MiB heap.
It verifies the APK signature/alignment/package/permissions. Only the signed
APK, hashes and public verification data are uploaded; not the signing key.

Primary references:
- https://perfetto.dev/docs/reference/perfetto-cli
- https://perfetto.dev/docs/concepts/config
- https://github.com/google/perfetto/blob/v48.1/protos/perfetto/config/trace_config.proto
- https://github.com/google/perfetto/blob/v48.1/src/perfetto_cmd/perfetto_cmd.cc
