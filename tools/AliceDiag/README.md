# ALICE Pin & Lag Lite 1.1.0

Read-only local diagnostic APK for S8+ / One UI 8 (Android16). This version
replaces the expensive per-node `cat` readers with shell builtins. Periodic
collection never calls dumpsys/gfxinfo, awk, getprop or cat. One optional `ps`
is allowed every 60s in lag mode / 5min in battery mode. Configuration and
frame summaries are one-off startup/end snapshots, outside the sample loop.

- Battery: sample, then rest 60s; at most 24h elapsed, no wakeup alarm.
- Lag: sample, then rest 15s; 10min maximum. A sample >=750ms increases the
  rest to >=30s, >=2000ms to >=60s. Backoff never decreases in a session.
  There is no subtract-cost or catch-up loop. Root commands time out in 5s.
- CSV includes `collector_ms`, `next_delay_ms`, `usage_access`, screen/charging
  state, reported battery values, memory and thermal status. Large suspend
  gaps remain missing; valid drain accounting excludes charging boundaries.
- `api_current_ua_reported` is stored verbatim. Some ported ROMs return the
  driver's mA scale through an API documented as microamps; this app does not
  auto-convert or derive power/battery health from it. Sysfs values are raw.
- Optional KSU root provides CPU/GPU/PSI/reclaim/zram/process/wakeup counters.
  Unknown nodes are omitted. A failed root read disables further root reads.
- Optional usage access records only session package-resumed/paused and screen
  events. Missing access is explicitly recorded in CSV and events.tsv.
- Startup/end configuration records actual task-profile JSON and digests,
  cpuset permissions, CPU QoS limits, schedtune and known bootstrap status.
  This allows a skipped compatibility fix to be investigated without guessing
  whether the checksum was unavailable or the ROM was a different version.
- At end, only counts of a selected cpuset error in the latest 400 system log
  entries are retained; this is a window count, not a session total/rate.
  Raw logcat contents, screen text, messages, SSIDs, serial and location are
  never retained. Logs do include package/process names.

The visible foreground service has a stop action. No Internet, wakelock,
boot receiver, background tuning, MGLRU changes or automatic upload. Logs
survive interruption/reboot in private app storage; ZIP exports to Downloads.

The new application ID `com.halot455.alice.diaglite` installs alongside 1.0.0,
preserving old private logs despite the CI diagnostic signing key changing.
Stop the old recorder before starting Lite. UI label includes Lite.

Validation: actual script execution with external readers instrumented,
Java drain-accounting/backoff tests, Android build/lint, Android16 emulator
foreground service/usage access/stop/ZIP export, and shell-sampler timing.
Emulator timing is not a real S8+/KSU overhead or battery-life measurement.
CI signing uses a diagnostic debug key, not a production update-signing scheme.

Build: JDK17, SDK35, Gradle8.9, AGP8.7.3; runs on Android8+. No runtime libraries.
