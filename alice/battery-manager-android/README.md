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

## First install / auto-start (ESG1 v1.1)

The 80/20 kernel interface is read-only; **LZ4KD is the kernel's default ZRAM compressor** (build config `CONFIG_ZRAM_DEF_COMP_LZ4KD=y`), and Samsung's ESG1 ramdisk fstab does not override its compressor. The APK enables AUTO, monitoring and notifications on **first application launch**, and registers a BOOT_COMPLETED receiver to restart monitoring after later reboots. Android requires opening an installed app at least once and explicitly approving SU in Magisk/KernelSU/SuperSU; installing an APK and immediately rebooting before ever opening it cannot bypass these security restrictions. To control Android standard Battery Saver, click the one-time root prompt. No Samsung status-bar rewrite, Samsung-specific UPSM, or physical battery capacity manipulation is claimed. Disable Samsung battery optimization for this app if the ROM stops foreground monitoring.

## 2026-11-16: Virtual battery icon and automatic safe emergency

- A pinned foreground notification shows a dynamic **numeric status-bar icon** for the virtual percentage. At the emergency threshold (real 24% = virtual 5%) the numeric display switches to **real 24%** as requested. This is an additional ALice notification icon, not a replacement for Samsung's system battery icon.
- Android Quick Settings tile `Pin ảo ALice` shows real/virtual SOC. Add it manually from the Quick Settings edit panel, as Android does not allow apps to forcibly add tiles without user action.
- Root-approved kernel bridge reads the five read-only `/sys/kernel/alice_battery_reserve` attributes when they are invisible to ordinary Android apps. The launcher shows whether kernel sync is available. Otherwise the APK uses the fuel gauge and its own persistent latch.
- The app enters its emergency state **at real 24% while unplugged** and automatically requests Android's *standard* Battery Saver through a fixed `su -c 'cmd power set-mode 1'` call; it does not reboot the phone. It persists the latch and releases it only after charging to true 100% and unplugging. Android / Samsung may reject the root command; the app logs the result. Kernel-side CPU constraints only exist if the 80/20 kernel has booted successfully.
- The proprietary Samsung **Emergency Mode / UPSM Home** still requires platform-signed Samsung services and a user consent flow on many Galaxy S8 builds. Samsung's published instructions require activation from the Power menu and acceptance of terms. This APK does not misrepresent standard Android Battery Saver as Samsung UPSM, and does not bypass the consent screen.
- The notification service responds to battery-level and cable-state broadcasts, otherwise polls once every minute; su saver attempts are throttled to one per three minutes to prevent unnecessary power use. Startup requires opening the app once and granting root once. Boot receiver restarts the monitor afterward.
- No change to the BOOT image or DTB in this APK-only update; do not treat a successful APK build as proof that the separate BOOTFIX kernel boots on the user's ROM.

## SystemUI Samsung battery icon bridge (v1.2 test / Xposed module in same APK)

- **No flashing BOOT for the icon update.** The APK is both the ALice dashboard and an Xposed/LSPosed *legacy* module. It targets only `com.android.systemui`.
- After installing the APK, open the app once; grant root in Magisk/KernelSU if supported on the ROM. In Xposed/LSPosed Manager enable **ALice Battery 80/20** and select scope **System UI (`com.android.systemui`) only**, then restart SystemUI / reboot. Do *not* add `android` or `system_server` to the scope.
- In the dashboard choose **Yêu cầu bật pin ảo trên biểu tượng Samsung**. It stores a UI-only Android Settings.Global flag by one allow-listed `su` command. The monitor also sends `real / virtual / emergency / full-seen` integers to similarly namespaced settings upon battery-level changes, never to `/sys/class/power_supply/battery/capacity`.
- The SystemUI-only hook tries the known BatteryMeterView callback classes and, if absent, a narrow legacy battery drawable callback. Newer/modified Samsung ROMs may have different class and method names; this cannot be guaranteed **without the original SystemUI.apk from this ROM**. The hook is designed fail-open: unknown classes leave stock real percentage unchanged. See LSPosed / Xposed logs for `[ALice80/20]` and count of attached methods.
- At real **60%** the visual should become **50%** virtual. At **24% real** (5% virtual, unplugged), it should show **24% real** and keep reserve status. If actually charged to 100% then unplugged, it should revert to the virtual scale. Charging, battery service, battery safety and actual Android `BatteryManager` report real SOC.
- **Emergency mode:** on reserve, APK requests *standard Android Battery Saver* through its authorized root command. This is not the proprietary Samsung UPSM Home screen; root + generic callback hooks are not proof of Samsung UPSM activation. No reboot or shutdown is requested at the reserve threshold.
- If any SystemUI crash / missing status icons happens: disable the module's **System UI** scope in Xposed/LSPosed, then reboot. Alternatively, the app's **Khôi phục biểu tượng pin thật Samsung** only disables the visual hook through `settings put global alice_8020_hook_enabled 0`, when the app/GUI is still responsive.
- Android debug APK CI signing may vary by run: if installing a new build reports a signature mismatch, uninstall the previous ALice dashboard APK first (this clears settings) and reinstall, approve root, and enable the module again.

**Known limitation:** this is a compiled, generic SystemUI class-hook TEST; no device-specific `SystemUI.apk` has been supplied or examined. A successful GitHub Actions APK build does not prove that an unknown Samsung variant's battery icon changes or that it is safe to apply universally.
