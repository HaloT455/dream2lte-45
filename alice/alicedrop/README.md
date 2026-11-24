# AliceDrop 0.1-alpha — Galaxy S8+ / ALice
This is a real Android prototype, not a working native AirDrop port.
- Detects Wi-Fi Aware availability and awdl0, discovers _airdrop._tcp on the current network for 10 seconds, and invokes Android's actual share sheet (Quick Share if installed).
- Optional local Safari file transfer in both directions, on the same trusted Wi-Fi, with a random session URL, 100 MiB limit and five-minute session. HTTP is not encrypted; do not use for sensitive files or untrusted networks. No iPhone app is required for this fallback. Save received file explicitly on Android. Original filenames are not preserved in this alpha.
- No background scanning, no root requests, no SELinux changes, no firmware replacement. Native AirDrop discovery/transfer is NOT implemented; it requires a validated AWDL or other compatible transport and Apple protocol backend.
- Kernel probe: scripts/alice_airdrop_probe.sh. BCM4361 firmware capabilities must be verified on the real handset before enabling any experimental radio code. Wi-Fi Aware/NAN is not equivalent to AWDL.
- Build: gradle -p alice/alicedrop :app:assembleDebug.

## Touch feasibility (0.2)
A foreground-only NFC reader probe detects a standard NFC tag without reading its contents, vibrates and offers the normal Android share sheet. This does not trigger Apple's AirDrop or NameDrop; no native Apple handshake is implemented. The probe times out after 20 seconds and stops when the app loses focus. Capability diagnostics also check HCE, the public NFC polling annotation API by reflection, and awdl0/mosey0. Missing interface while idle is not proof of unsupported firmware.
References: https://github.com/CodingGenius0001/namedrop-android (NameDrop contact exchange on Android 17/S26; not arbitrary file transfer), https://developer.android.com/reference/android/nfc/NfcAdapter, https://github.com/seemoo-lab/owl. Android 16 on S8+ and its NFC/Wi-Fi firmware need validation before a native touch implementation can be attempted.
