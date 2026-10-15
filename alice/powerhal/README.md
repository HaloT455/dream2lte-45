# ALICE Power HAL R12

Replacement for the audited Samsung AIDL V2 service, with a bounded CPU QoS
backend for the Exynos8895 EnergyStep kernel. The boot action only installs when
the original service SHA256, SELinux executable label, manifest version and
service layout match. Unknown ROMs retain their existing service.
An isolated, finite startup guard checks `backend=ready`; if this cannot be
established, it unmounts the replacement, restarts the original service and
creates the disable marker. It does not block Android's init action queue.

Supported modes: LOW_POWER, LAUNCH, INTERACTIVE, DEVICE_IDLE, DISPLAY_INACTIVE.
Supported boosts: INTERACTION and DISPLAY_UPDATE_IMMINENT. Unsupported modes and
boosts report false. LAUNCH expires within 1000 ms even without the matching
disable callback; interaction expires within 250 ms (80 ms default). Low power
limits added floors to the little cluster, rather than setting a fixed CPU cap.

HintSession V2 reports feed a deadline-ratio controller with a deadband. Each
session owns a distinct slot (maximum 16); reports lease an added floor for
40–250 ms. Closing, pausing, target changes and Binder destruction release it.
Missing reports expire in the kernel. The framework must validate thread/UID
ownership before creation; only UID 1000/root may create sessions. No arbitrary
task affinity, scheduling priority, uclamp or scheduler feature is emulated.

Floors in kHz (little/big): level 0 = 0/0, level 1 = 949000/0,
level 2 = 1053000/1066000, level 3 = 1248000/1261000. Native EnergyStep may run
above those floors according to workload. Other clients' QoS requests remain
independent. Native thermal/max-frequency constraints still override the floor.
Added boost is restricted to level 1 at CPU >=60 C, and removed at >=65 C or
when either CPU temperature sensor cannot be read. These rules only govern the
new floors; native thermal trip temperatures/voltages remain unchanged.

Screen-off, device idle, display inactive and suspend clear all leases. The
kernel worker runs only while a lease is pending, checking temperature at most
every 200 ms. There is no userspace polling daemon or model inference.

Build inputs are public AOSP AIDL API snapshot V2 (hash
`ef4f5ed58e39693f25c1f8fdcfe7b958c6b800bc`), AOSP platform NDK service headers,
and official Android NDK r27d (27.3.13750724). libc++ is statically linked. A
build-only libbinder_ndk symbol stub is never installed; the service links to
the ROM's real libbinder_ndk.so, liblog.so, libc.so, libm.so and libdl.so.
VINTF Binder stability is enabled. No proprietary vendor binary is committed.

AIDL source snapshot:
https://android.googlesource.com/platform/hardware/interfaces/+/1a56e38edc2f2f6189ef405ee1edce554e15cbc0/power/aidl/aidl_api/android.hardware.power/2/

Platform headers (Apache-2.0):
https://android.googlesource.com/platform/frameworks/native/+/refs/heads/android13-release/libs/binder/ndk/include_platform/android/

Host checks execute the actual deadline controller and kernel endpoint with
substituted clocks/thermal/QoS APIs. They establish control-flow/expiry behavior,
not Binder delivery, init namespace propagation, SELinux permission, boot
success, frame time or battery improvements on the phone.

After flashing check:
```
adb shell 'su -c "cat /data/adb/alice-powerhal/status.log; cat /sys/power/alice_power_hint; dumpsys android.hardware.power.IPower/default"'
```
The dump should say `backend=ready`; `session_created` and `report_batches` show whether ADPF sessions/reports actually reach the HAL. An unchanged `commands` count means no
delivered hint has been established. App ADPF use depends on framework/app
support; this does not add ADPF support to applications that never send hints.

Rollback just this service, leaving the R12 kernel/CPU fixes active:
```
adb shell 'su -c "touch /data/adb/alice-powerhal/disable; reboot"'
```
The bind mount is temporary. The original vendor image is never written.
