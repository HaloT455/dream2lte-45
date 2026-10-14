# R10: AdGuard and associated-network preference embedded in boot

The user requested automatic AdGuard without a separate module, fewer Wi-Fi
network switches after manual selection, and continued automatic connection.
The earlier DNS module alone did not satisfy the requested boot integration.

The supplied boot has a first-stage Android init ramdisk: init, fstab and
dpolicy, with no init.rc. Merely adding a root init.rc would not demonstrate
that the actual second-stage system init reads it. R10 instead extends the
existing KernelSU init.rc injection with a disabled, oneshot alice-netboot
service. It uses KERNEL_SU_DOMAIN (ksu), whose policy rules the existing hook
already installs before the RC read. No new domain or global permissive mode
is introduced. The script is embedded as base64 in the linked RC, materialized
with root-only permissions in /data/adb/alice-netboot, then executed as shell.
The zygote-running event starts it early; boot_completed supplies a later
attempt if needed. Init will not start a second copy of a running service.
Tasks are finite: at most 30 attempts with 2-second gaps per service run.

## DNS

When SettingsProvider is ready, set private_dns_specifier=dns.adguard-dns.com
and private_dns_mode=hostname. Preserve the initial previous pair, verify
settings readback, and attempt rollback on partial failure. This uses Android
DNS-over-TLS and still appears in the Private DNS UI; no manual setting or
DNS module is needed. It does not run before Android services are available,
and readback is not proof of successful TLS/network validation or ad blocking.
The global setting persists for subsequent boots. DNS cannot block every ad
or applications that use a different resolver.

## Wi-Fi

The actual AOSP WifiShellCommand accepts:

    cmd wifi set-network-selection-config enabled enabled -a 2

The two sufficiency checks stay enabled. Associated selection override 2
asks the framework to stop automatically choosing a different network while
already connected. Disconnected selection/autojoin and saved network records
are untouched. Manual selection remains available. No BSSID pin is added and
firmware roaming within the same network remains unchanged. This does not
promise which saved network an OEM picks after a disconnection or reboot.
The script checks the advertised command and override syntax, skips unsupported
OEM APIs, and logs REQUESTED rather than falsely claiming device verification.

No TX power, country code, NVRAM, antenna-chain, firmware, or driver change is
made. There is no measured increase in reception range or RF gain. This
preserves hardware/regulatory limits and the existing CPU/GPU thermal policy.

## Control and limits

Logs: /data/adb/alice-netboot/status.log. A disable file in that directory
prevents future startup actions. Running its boot.sh restore creates disable,
restores DNS if still owned, and requests Wi-Fi override 0 (platform default),
not an unknown previous custom Wi-Fi configuration. User-changed DNS is kept.
Flashing an older boot does not by itself remove persisted DNS settings.

Host checks compile the actual KERNEL_SU_RC declaration, decode and execute
the exact embedded bootstrap, and exercise DNS rollback, absent services,
bounded retries, repeat boots, restore, unsupported Wi-Fi commands, preservation
of autojoin/SSID, and late readiness. CI checks the complete payload in the
linked ARM64 Image. These checks cannot prove boot, OEM policy, DNS validation,
signal range, temperature or battery results on the phone. R9 device boot and
the earlier Samsung-logo reboot root cause remain unconfirmed.

MGLRU OFF, PSI bootstrap repair, original worker member offsets, EAS/EnergyStep,
GPU -5 bias, native thermal limits, KSU 32590 and Enforcing remain unchanged.
The companion memory module accepts R10; DNS/Wi-Fi do not require that module.

Primary references:
- https://adguard-dns.io/en/public-dns.html
- https://android.googlesource.com/platform/packages/modules/Wifi/+/refs/heads/main/service/java/com/android/server/wifi/WifiShellCommand.java
- https://android.googlesource.com/platform/packages/modules/Wifi/+/a554f2225ae6b52a9132aed29926632f0f093f60
