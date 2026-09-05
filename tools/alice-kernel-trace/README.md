# ALice Kernel Trace 2.0

Diagnostic companion for the ALice V8 MGLRU + SimpleLMK kernel on Samsung
Galaxy S8+ (`dream2lte`). The app does not tune or modify kernel parameters.

## Recording behavior

- Runs as a foreground service and writes logs directly to app external storage.
- Enforces a 60-second minimum before **Stop and save** is enabled.
- Continues recording across screen-off without holding a wakelock, so suspend
  failures can still be reproduced.
- Stops automatically after 15 minutes to cap storage use.
- Best-effort root collectors: rotating all-buffer logcat, streaming dmesg,
  one-second memory/CPU/thermal samples, start/end snapshots, and a 64 MiB
  Perfetto trace.
- Syncs files every five seconds and on screen-off/shutdown broadcasts.
- A `RUNNING` marker is retained until a clean stop. On the next boot or app
  launch, an interrupted session is paired with pstore/last_kmsg/current boot
  diagnostics and exported as a recovered ZIP.

Logs are stored under the app's external files directory in
`ALiceKernelTrace/`. Uninstalling the app removes this directory, so share the
ZIP before uninstalling.

## Recommended test

1. Install the APK and grant root in KernelSU.
2. Tap **Check kernel / root / SIM**.
3. Start recording and turn the screen off for at least 60 seconds.
4. Wake and unlock the phone. If it survives, tap **Stop and save ZIP**.
5. If it reboots, unlock once, open the app, and share the recovered ZIP.

Logcat may contain app names, phone numbers, or notification text. Review the
ZIP before sharing it.
