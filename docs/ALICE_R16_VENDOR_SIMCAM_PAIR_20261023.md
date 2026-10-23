# ALICE R16 + Vendor A16 SIM/Camera source pairing — 2026-10-23

**Pair ID:** `ALICE-S8P-A16-R16-SIMCAM-20261023`

**Evidence:** uploaded known SIM-working `boot.img` uses Galaxy S8+ (dream2lte), Linux 4.4.302, interactive governor, DH2 stage51/HMP scripts in old ramdisk; vendor.new.dat.br decodes to EROFS 499060736 bytes. Known modem symbols from extracted boot IKCONFIG are retained in R16 defconfig: SEC_SIPC_MODEM_IF, SEC_MODEM_SS310AP, UMTS_MODEM_SS310AP, LINK_DEVICE_NAPI, LINK_DEVICE_SHMEM, MODEM_IF_QOS, SHM_IPC and EROFS.

**Peer:** `HaloT455/Vendor-45-` branch `work/a16-r16-paired-sim-camera-20261023` built on prior Samsung camera/Video6 working candidate and Test7 original RIL. Peer CI checks pinned R16 source commit `b892e28db47fb9aaf2df8d3196050a76288b6caf`.

## Concrete compatibility protection

- `scripts/guard_boot_vendor_pair.py`: static kernel/vendor handshake for modem config, radio HIDL and native binaries, Camera Video6 metadata, per-slot network defaults, optional owner reference boot image SHA, legacy ramdisk warning.
- `scripts/repack_boot_v0.py`: R16 EnergyStep image will no longer silently reuse a DH2/interactive/HMP ramdisk. Repack refuses that combination unless manually overridden with the **dangerous** `--allow-legacy-hmp-ramdisk` option. Such an override is not a validation or recommended deployment.
- `scripts/test_r16_legacy_ramdisk_guard.py`: host regression must prove the rejection and acceptance of a clean test ramdisk before CI kernel packaging.
- `.github/workflows/alice-v12r69-baseline-build.yml`: source-pins matched Vendor tree and runs guard, then builds R16 Image and dtb.img, publishes checksums and report.

**Artifact:** `ALICE-S8P-A16-R16-PAIR-KERNEL-SIMCAM-UNTESTED-<commit-sha>` (Image/dtb; not flashable boot.img).

## Restrictions

No kernel drivers, radio firmware, CP, EFS, IMEI, SELinux, modem calibration, or Camera HAL are modified. This source-synchronized pair is an untested research build, not a device-proven stable boot+vendor release. Green CI never establishes two SIM registrations or recorder operation. Before flash: check partition size, verified TWRP recovery, compatible boot ramdisk and real phone testing.
