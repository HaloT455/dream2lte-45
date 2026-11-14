# ALice Battery 80/20 — Galaxy S8+ ESG1 companion (TEST)

Standalone Android application (min Android 8.0; target 32) for rooted
Samsung Exynos8895. No Magisk/KernelSU module required if root is already
available through `su`. Foreground service and boot receiver monitor battery.
The app can run read-only when root is not granted.

Features: real and virtual %; 5% virtual maps to 24% real; read-only kernel
sysfs display/lock if present; 100% real full-then-unplug latch; temperature,
voltage, measured current, USB input voltage when exposed; AUTO and CUSTOM
Android **standard** Battery Saver via `su -c 'cmd power set-mode 1|0'`;
custom threshold, notifications, persistent foreground status and event log.

The app never writes kernel capacity, voltage, thermal, GPU/CPU frequency, or
charger current. The Samsung-specific "Restrict apps and Home screen" UPSM UI
and the Samsung status-bar percentage cannot be forced from an ordinary APK
or kernel alone. Root only controls Android standard saver if ROM supports it.

The kernel has a fixed reserve lock at real 24%; custom mode does not bypass
that protection. No promise of physical battery partitioning or extra energy.

Build: `gradle :app:assembleDebug` with JDK17, AGP 8.7.3, Android SDK35.
Root permission must be explicitly granted in Magisk/KernelSU/SuperSU when
the app attempts `su`. This is a test, not phone-verified software.
