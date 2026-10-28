# Android 17 / One UI 9 — boot integration on Galaxy S8+ Exynos8895

### Existing proven boot

The user-reported ROM boots successfully on One UI 8 with:
`4.4.302-Alice-V12R5T-MGLRU-KSU32590-Enf+` on `SM-G955F rev05`.

A real SYSTEM One UI 9 Stage1 hardware test produced a `last_kmsg` showing:
- kernel passes early hardware initialization, detects Exynos8895 and starts
  `init` as PID1;
- `/system/bin/secilc` reads both platform/vendor policy files and errors
  at a duplicate `genfscon sysfs /bus/usb/devices`;
- PID1 aborts in `SetupSelinux`, then kernel panics at ~3.6s.

The kernel panic is **secondary to failed userspace SELinux policy assembly**.
There is no evidence from this test that the 4.4 kernel fails hardware boot
or that replacing it will fix this specific crash.

### Port release order (verified hardware security)

1. Use the *actual known-booting* Enf boot.img as the rollback baseline,
   with sha256 and partition-size checks. It is not present as a verified
   identical base boot artifact in this Git tree.
2. Align SYSTEM Android17 platform policy with VNDK33 Exynos8895 vendor
   SELinux policy and mapping. **Do not disable enforcing/neverallow**.
3. Run Android17 native `secilc` test on ARM64 and then the device's
   unmodified first-stage init on a quarantined research device.
4. Only if a kernel/ramdisk-specific incompatibility is observed, rebuild
   an `enforcing` kernel with current working configuration and repack via
   `scripts/repack_boot_v0.py` from the actual reference boot; preserve
   header, DT, ramdisk and footer.
5. Validate Graphics Mali-G71, cameras, telephony and hardware-backed
   Keystore/Gatekeeper after first-stage and services actually start.

**Do not flash an altered boot image simply to fix the observed CIL error.**
Do not use a permissive kernel for a device containing financial accounts.

### Related private technical evidence

- https://github.com/HaloT455/Dre/issues/1
- https://github.com/HaloT455/Dre/actions/runs/40616204342
- https://github.com/HaloT455/Dre/actions/runs/40616877172

STATUS: `BOOT_KERNEL_EARLY_STAGE_WORKS`, `SYSTEM_SEPOLICY_BLOCKED`,
`A17_BOOT_READY=NO`.
