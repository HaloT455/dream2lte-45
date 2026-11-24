# Aura Android13-9 SM-G955F donor boot audit (user-supplied `boot(1).img`)

This folder records a **real, forensic comparison**, not a claim to have
reconstructed proprietary source from a compiled boot image.

## Identified donor

- Supplied image: 41,943,040 bytes (40 MiB), SHA-256
  `80003cebe663f62683b28d864e73482ff379e6d52418a9eaa5897595a1bd1250`.
- Kernel: `Linux version 4.4.302-android13-9 (hlong@aura)`,
  GCC 12.2.1, built October 14, 2026. ARM64 Image: 35,213,912 bytes,
  SHA-256 `e3a1b66cd58c0501729a65fd40740567ad6703a9ca1604b242a59bab5946c4fc`.
- Board in real DTB: `Samsung SM-G955F rev05`; Samsung `DTBH`
  v2, one DTB. DTB SHA-256
  `078769b216aaa973f9f6aa2d7ae08d8d62461083834f6c1fb230a2f9b177d40e`.
- Ramdisk gzip/newc CPIO: 700,086 bytes, SHA-256
  `156c66be8d36f112a24c15f4e87e320c471e246ad6666e57f56ac53952f08624`.
- Android boot v0-like header, 2,048-byte page, recomputed SHA-1 matches.
  File has `SEANDROIDENFORCE` and an `AVBf` footer at the last 64
  bytes. Approximately 5.8 MiB lie after the declared Android boot data.
  **Do not copy this footer/signature into a modified ALice image**:
  it must be regenerated/verified with the appropriate boot-chain keys.

## Differences versus ALice Samsung EGO (`fd35b3c`)

| Feature | Donor boot(1).img | ALice EGO | Decision |
|---|---|---|---|
| CPUFreq governor | `interactive` default; `blu_active` enabled | `energy_aware` only | **Do not import**: conflicts with Energy-Aware requirement |
| Scheduler | HMP and task-based softlanding; WALT off | Energy-Aware's native scheduler hooks and WALT | **Do not import** unrelated HMP scheduling |
| A53/M2 frequency ceiling in DTB | 1,794 / 2,574 MHz | 2,002 / 2,704 MHz | Retain user's requested ALice limits |
| Samsung energy-cost references in CPU DT | Absent | Present with 12+17 EGO candidates | Retain ALice |
| APOLLO thermal thresholds | 76/81/86/... °C | 65/70/75/... °C | **Do not import** elevated limits or weakened cooling maps |
| KernelSU | `CONFIG_KSU=y`; LSM hooks and always-threaded throne tracker | `CONFIG_KSU=y`; native 4.4 auto LSM hooks (new), boot tracker remains synchronous | **Imported mechanism from existing ALice KernelSU source:** native list registration instead of pointer hijacking; disabled duplicate manual sites; details in `alice/KERNELSU_AUTO_LSM44.md` |
| Memory | legacy Android lowmemorykiller, zswap, vnswap | LRU_GEN/PSI and LZ4KD zram | Do not combine competing memory schemes without source and tests |
| Networking | MPTCP enabled | not built; existing legacy source in `net/mptcp/` | Evaluate disabled Kconfig/build integration and Android/peer protocol compatibility before enabling; no donor binary code copied |
| Mali GPU | `CONFIG_MALI_VK_BOOST=y` | no such option in ALice | Not portable from binary alone; source/driver version required |
| Fstab SYSTEM/PRODUCT/VENDOR | EROFS-only | EROFS and ext4 fallback | **Imported as opt-in ROM profile** |
| Zram fstab entry | 2,684,354,560 bytes, 8 streams | 3,435,970,560 bytes, 4 streams | Preserved in opt-in ROM profile; not changed in default ALice |

The additional KernelSU automatic hook adaptation is tracked in [`alice/KERNELSU_AUTO_LSM44.md`](../../KERNELSU_AUTO_LSM44.md). Unlike the EROFS profile, it changes the compiled kernel configuration. It was implemented from the ALice KernelSU source because the uploaded binary does not contain rebuildable source.\n\n## Actually imported (no fake feature claims)

`fstab.samsungexynos8895` in this folder was extracted byte-for-byte
from the donor boot's gzip/newc ramdisk and Git blob hash verified:
`d1dae668dd63283d86c63fc76c2203c519af6bdb` (2,409 bytes).
Original SHA-256:
`6dcd1280873f6628f8d4392c2679f42bec170ec85f849c3f16b302fd257c8d60`.

It is **an optional EROFS Android13 ROM profile**, *not* the default
ALice ramdisk and **not** an automatic change to compiled kernel behavior.
Use only if the device's installed ROM really mounts SYSTEM/PRODUCT/VENDOR
as EROFS. Preserve the currently working boot/ramdisk otherwise.

### Further investigation

A kernel binary plus a `.config` identifies what was enabled, but does
not reveal enough source to safely transplant MPTCP, HMP, Mali Vulkan
boost or KernelSU security integration. Locate the corresponding GPL
source and inspect its driver dependencies before attempting those ports.
For thermal trip/cooling tables, retain the ALice DTS safeguards instead
of importing the looser donor configuration.

A passed kernel CI build is not physical evidence of Android boot or OC
stability, and an `AVBf` footer is not evidence of valid signatures
for another kernel.

## Follow-up source inventory

ALice already has `drivers/staging/android/freecess.c`, `freecess_pkg.c`, `include/linux/freecess.h`, `net/mptcp/`, legacy zswap and vnswap source. These are not evidence that the features are linked or safe to enable. Freecess needs matching Samsung userspace; MPTCP needs protocol/peer and integration checks; keep LRU_GEN/PSI/LZ4KD as the default memory design. The donor and ALice compiled configurations both select Mali r19p0; donor `MALI_VK_BOOST` has no verified corresponding ALice implementation yet. No donor KernelSU code is imported. Original ALice KernelSU v3.2.5+ remains pinned to HaloT455/KernelSU master e874376f71d80c6ee4163fafdc03e62412adbc49, with the local ALice auto LSM adaptation retained.
