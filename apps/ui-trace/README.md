# ALice UI Trace 1.0

Native Java Android APK for one user-initiated **60-second** UI trace with root.
Android 8+; compile/target SDK 35. No third-party app dependencies, INTERNET,
storage-management, accessibility, installation, wake-lock or boot receiver
permissions. It does not install root or grant itself root.

1. Flash the matching UI1-Trace boot. This app cannot add missing kernel tracing.
2. Install APK; open **Cấp root / kiểm tra kernel** and approve it in KernelSU.
3. Press **Ghi log 60 giây**. The app goes into the background with a notification;
   after a three-second preparation, reproduce the stutter. USB is unnecessary.
4. Return to the app; tap the saved log to share it. **Dừng ghi sớm** also appears
   in the recording notification. Keep the app's task; swiping it away cancels.

Trace data is buffered in RAM (8192 KiB per CPU, up to 64 MiB on dream2lte),
then exported after recording. Metadata can be written before recording.
This is a rolling buffer: the app reports nonzero overruns/dropped events.
Formatted log output is capped at 128M characters; truncation is reported.
Logs remain private to this app, are not automatically deleted or uploaded,
and can be shared read-only via a non-exported, grant-controlled provider.
Uninstalling/clearing app data removes those logs; share them first.

Root commands are fixed: check UID/kernel, execute the packaged bounded
collector, or terminate the exact owned script PID after verifying its unique
script path in `/proc/PID/cmdline`. There is no arbitrary-command UI, no policy
or permission weakening, no frequency/thermal/sysctl writes, and no background
daemon installed. Stop any other trace session before recording.

The collector restores atrace to its stopped defaults on completion and on
trappable interruption. A 150-second watchdog requests cancellation if setup,
capture or dumping hangs. SIGKILL, process death and reboot cannot guarantee
cleanup; if cleanup fails or a capture hangs, reboot before normal use and
share the partial log. Logs may contain process/app names and diagnostic
metadata. Only share them with someone you intend to receive them.

This is a diagnostic tool, not the final performance kernel, not a continuous
logcat recorder and not a guarantee of retaining a kernel crash after reboot.
Hardware root access, recording, UI and sharing require on-device verification.

Build: `bash apps/ui-trace/build.sh` with JDK 17, Android SDK platform 35 and
build-tools 35.0.0. CI signs with a fresh private diagnostic key and uploads
only the signed APK, its hash and public verification data. Rebuilds may require
uninstall/reinstall because signing keys are intentionally not published.
