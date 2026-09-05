# ALice V8 compatibility contract

## Scope

V8 targets the Galaxy S8+ `dream2lte` variants `SM-G955F` and `SM-G955FD`.
The kernel keeps Samsung's Exynos8895 hardware glue, device tree, modem IPC,
power-management fixes and thermal controls. It is not intended for other
Exynos8895 devices without a separate device-tree and boot validation pass.

## AOSP and One UI

The same kernel image exposes `binder`, `hwbinder`, and `vndbinder`, and keeps
ashmem, cgroups, namespaces, SELinux, F2FS, EROFS and overlayfs. The flashable
package replaces the kernel and DTB while preserving the currently installed
ROM ramdisk and command line. This removes the main source of avoidable
One UI/AOSP boot incompatibility.

One UI still requires its matching Samsung vendor partition. AOSP still
requires the device's matching vendor blobs and init configuration. A kernel
cannot replace either ROM's userspace dependencies.

## Scheduler provenance

The core EAS/schedutil files on the V8 base were checked against Google's
Android 4.4 EAS tree. CI pins the audited hashes of `kernel/sched/fair.c` and
`kernel/sched/cpufreq_schedutil.c`. Samsung-specific Exynos topology, DVFS,
cpufreq and thermal glue remains because replacing it with generic code would
remove hardware control rather than improve the scheduler.

## Memory policy

MGLRU performs page aging and eviction. SimpleLMK remains a pressure-response
backstop for Android process killing. The legacy Android in-kernel LMK is kept
disabled so two independent kill policies do not compete.

## Dual SIM and IMS

The device tree exposes both RIL IPC endpoints (`umts_ipc0` and `umts_ipc1`),
dual-SIM detection, and `rmnet0` through `rmnet7`. CI verifies these interfaces
on every V8 build.

This is the kernel-side transport required for LTE data on either SIM. VoLTE
and VoWiFi registration additionally require compatible modem firmware,
Samsung vendor RIL/IMS or an equivalent AOSP IMS stack, carrier provisioning,
CSC/MBN configuration and ePDG support. V8 does not falsify IMS registration
or force unsupported carrier profiles.

## Flash and rollback

CI produces separate enforcing and permissive AnyKernel3 ZIP files. They patch
the current boot partition in place and preserve the ROM ramdisk. Back up the
working boot partition before flashing. Enforcing is the normal build;
permissive exists only for diagnosis.
