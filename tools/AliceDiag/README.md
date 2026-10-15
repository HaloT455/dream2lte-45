# ALICE Pin & Lag 1.0.0

Local diagnostics for the S8+ / One UI 8 EnergyStep investigation. This is a
separate app from the old MGLRU Diag app: it never enables MGLRU or changes any
kernel/ROM setting.

- **Pin:** user-started 24-hour session, samples every 60 seconds while the
  process is scheduled. No wakelock, wakeup alarm, boot receiver or network
  permission. The device may suspend naturally: samples can be far apart, and
  the recorder ends at its next scheduled run/wake after the elapsed limit.
- **Lag:** 10-minute session, 5-second sampling; process/wakeup/foreground-frame
  summaries at most every 30 seconds. No gfxinfo or batterystats counter reset.
- Battery percentage, temperature, voltage, current µA, charge µAh, charge state,
  screen state, elapsed/awake clocks, Android thermal status and available RAM.
- Optional KSU root: raw CPU frequency/residency/limits, GPU load/frequency,
  thermal sensors, PSI, zram, reclaim counters and process CPU cumulative time.
  Every root command is bounded in time and output. A failed root command
  disables root reads for that session rather than repeatedly requesting root.
- Optional Android usage access: resumed/paused package and screen events from
  the session only, with timestamps. No class names or notification content.
- One ZIP exported via MediaStore Downloads on Android10+; document picker on
  Android8–9. Logs survive interrupted recording/reboot inside private storage.
  Sessions are limited to 32MiB before the next sample; individual root outputs
  to 512KiB. Old sessions remain until the explicit delete button is used.

There is a visible foreground-service notification with a stop action. Root
and usage access are optional; unavailable readings remain missing. No
analytics, Internet, accessibility service, screen capture, location, SSID,
accounts, contacts, messages, serial or raw logcat collection. Logs reveal
package/process names and should be shared only deliberately.

`battery.csv` records measurement cost, so overhead can be assessed. Battery
rate excludes charging transitions, missing readings, >3% capacity jumps, and
sampling gaps >3 minutes. It is only shown after >=30 minutes of valid samples
and >=2% drop. It does not estimate battery health or promise 24–36h runtime.
`usage-events.csv` event constants: 1=resumed, 2=paused, 15=screen interactive,
16=screen not interactive. Multiwindow events need interpretation; they are not
automatically converted into exclusive foreground durations.

Checks: executable Java drain-accounting cases; Android lint/build; API35
emulator launch/foreground service/stop/export with root absent. KSU permission,
SELinux access, Samsung sysfs coverage and long-run overhead require the phone.

Build: Java17, Android SDK35, Gradle8.9, Android Gradle Plugin8.7.3. No app
runtime dependencies. CI publishes a public prerelease APK built only from
this source. Debug-key signing is for this diagnostic build, not a production
update-signing guarantee.
