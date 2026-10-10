# K510 P6 — actionable *full-function* migration plan (V12R5T Linux 4.4.302 → Linux 5.10 / Android 16)

Status: **engineering plan and dependency graph, not a complete port or flashable build.**
Target: Samsung Galaxy S8+ SM-G955F, Exynos8895 (dream2lte), One UI 8 / Android 16, EROFS system/vendor.
Known working rollback: V12R5T 4.4.302 BOOT SHA256 \`76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823\`.
Pinned donor kernel source: \`agent/v12r5t-mglru-aging-stability\`, commit \`3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3\`.
Target current source: genuine Linux \`5.10.262\` (P5 compile successful, GitHub Actions #38023753519).
Previous port status: P4 DTB base compiler-checked; P5 binder/EROFS/F2FS/SELinux/DM successfully compiled; R1/R2 **hung on static S8+ splash and had no provable Linux 5.10 boot record**.

## Evidence used; what it does and does not prove

* 2024 Exynos8895 mainline series supports CPUs/GIC/PSCI, pinctrl, GPIO, simplefb, pstore, minimal initramfs on **SM-G950F dreamlte**, NOT full S8+ Android:
  https://lists.openwall.net/linux-kernel/2024/09/09/753
* 2025 barebox S8 boot-shim proposal documents S-Boot quirks: changed stock DT, disabled DECON refresh, kernel placement/alignment, and potentially inadequate inherited stack. It uses **downstream DT from x0** to select board and relocate stack. This is **one boot-shim candidate**, NOT validated on this SM-G955F, and its mailing-list patch is not proof that it is merged to upstream:
  https://lists.infradead.org/pipermail/barebox/2025-July/051865.html
* Android documentation lists \`android12-5.10\` and \`android13-5.10\` common kernel lines among those compatible with Android 16. This is **platform-level support only**, NOT Samsung OneUI8 vendor HAL ABI compatibility:
  https://source.android.google.cn/docs/core/architecture/kernel/android-common?hl=en

## Critical architecture decision

Two branches must remain independent:
1. **K510-BOOT** uses current upstream 5.10.262 + minimal /init and compares **uniLoader** vs **barebox exynos boot shim** using observability. Must reach an objectively verifiable Linux 5.10 marker (serial/pstore validated; screen text from uniLoader alone is not enough). Never infer entry from a static splash screen.
2. **K510-ANDROID** uses Linux 5.10 with Android Common Kernel features as appropriate, then ports vendor drivers **from the exact working V12R5T donor**, adapts in-kernel APIs and preserves Android vendor/HAL interfaces. When evaluating ACK android13-5.10, do not assume its KMI permits loading old 4.4 modules; they MUST be rebuilt. Keep Android-upstream and old 4.4 code provenance in separate source folders, adapting one subsystem at a time.

Neither barebox nor vendor code transplantation is a substitute for a successful SoC boot and working storage.

## Dependency-driven milestones — NOT file-size driven

| Order | Work package, sources | Must implement / method | Required proof to unblock next stage |
|---|---|---|---|
| G0 | Boot shim, S-Boot DTBH, memory map, entry EL, cache maintenance; existing P1/P2 and 2025 barebox S8 proposal | Verify stock BOOT header/DTBH/hwrev/board-ID; preserved FDT passed in x0, early stack, 2MiB ARM64 entry alignment, guarded 64MiB kernel placement, no reserved memory collision; stage logging before Linux | Marker in **Linux 5.10** and /init; no writes to userdata |
| G1 | GIC/timer/PSCI/clock/pinctrl/UART + DTB V12R5T | Upstream SoC bindings + Exynos8895 clock/pinctrl backports; compare V12R5T 26MHz osc; use UART \`0x10430000\`, IRQ SPI385 only with confirmed safe pinmux | Linux kernel boot log and 8 CPU map (SMP only when safe) |
| G2 | Power foundation **S2MPS17** | Vendor \`drivers/mfd/s2mps17_core.c\`, \`drivers/regulator/s2mps17.c\` and related \`drivers/mfd/s2mps17*.c\`, platform \`include/linux/mfd/samsung/s2mps17*.h\`, Samsung ACPM MFD IPC driver + matching DT regulator supply phandles | All rails identified, read-only regulator status first; no unknown power rails driven |
| G3 | Embedded UFS | Vendor \`drivers/scsi/ufs/ufs-exynos.c\` plus SoC-private PHY/M-PHY, vendor UNIPRO tuning/calibration, sysreg + clocks/power; Linux 5.10 already has \`drivers/scsi/ufs/ufs-exynos.c\` (different Exynos7 binding/API); add Exynos8895 variant, **do not blindly replace** upstream source | First verified controller read-only probe, enumerate UFS LUNs, find BOOT by name, no unexpected writes |
| G4 | Android-first-stage storage | Native 5.10 \`EROFS\`, F2FS, device mapper, crypto/verity and encryption support; V12R5T initramfs/fstab logic with Android userspace and vendor mount expectations; do not copy mini heartbeat-only /init | Mount system/vendor and get logs from Android init (no data formatting) |
| G5 | USB Type-C / charger / fuel gauge | Vendor \`drivers/mfd/max77865.c\`, \`drivers/battery_v2/max77865_charger.c\`, \`drivers/battery_v2/max77865_fuelgauge.c\`, Samsung USB/Type-C/extcon integration and \`power_supply\` API updates; charger-off mode also needs Android userspace/LPM | TWRP vs 5.10 voltage/current/status comparison; USB enumeration; verified off-mode charge and thermals |
| G6 | Screen/input | Vendor \`drivers/video/fbdev/exynos/dpu/decon_core.c\`, DSIM and panel command source; convert legacy framebuffer paths, EXYNOS ION/IOVMM/SMMU, fences to usable Linux 5.10 DMA-BUF/DRM or explicitly maintain a compatibility implementation; preserve exact panel timings | Kernel-controlled panel after boot logo, touch buttons/input, screen-off resume |
| G7 | GPU/HWC | Vendor \`drivers/gpu/arm/tMIx/\` Mali-G71 Bifrost r19p0 + matching proprietary userspace HAL, ION heap names, DMA-BUF/IOMMU and sync ioctls; upstream Panfrost is a **separate userspace graphics stack**, not drop-in for Samsung Mali HAL | Matching Mali kbase API, successful HWC EGL tests, zero IOMMU faults |
| G8 | Modem/communication | CP firmware kept untouched; vendor Exynos SHMEM/SIT/RIL interfaces, SIPC/RMNET, radio wakelocks; audio ABOX + codec, Wi-Fi/BT firmware and PCIe/SDIO, NFC & sensors. Run per-driver probes | RIL recognizes modem, calls, data/WiFi/BT/audio, resume and no radio crash |
| G9 | Camera and remaining vendor services | Vendor \`drivers/media/platform/exynos/fimc-is2\`, ISP firmware, clocks, V4L2 API, SMMU mapping, Samsung camera HAL and stock services; fingerprint etc. | Camera HAL actually streams frame (not just recognizes node), working video/audio |
| G10 | End-to-end One UI 8 | Android init \`*.rc\`, uevent permissions, SELinux, VINTF/HAL, service transitions, memory/thermal, KSU if requested, OTA/backup | Cold boot, LPM, full device matrix, 24hr stability / battery logs verified on hardware |

### Port mechanics for each vendor subsystem

1. **Pin donor:** exact Git commit and file list. Preserve each source's license and SHA. Do not package OEM closed binary firmware in the repository.
2. **Extract dependencies:** old Kconfig/Makefile, includes, DT \`compatible\`, clock/reset/regulator/interconnect phandles, syscon registers, misc IOCTL/udev paths. Track each symbol in a manifest.
3. **Compare 5.10 facilities:** prefer upstream driver + a board-specific variant; otherwise place vendor code under a clearly named compatibility directory without disrupting generic drivers.
4. **Resolve ABI deliberately:** \`platform_driver\`, \`power_supply\`, \`regulator\`, \`i2c\`, \`devm_*\`, \`clk\`, \`dma_buf\`, \`IOMMU\`, \`v4l2\`, \`binder\`, \`selinux\` can differ from 4.4. A matching source filename is not evidence of ABI equivalence. Keep proprietary Mali userspace ABI invariant where possible.
5. **Dependency gate:** build \`ARCH=arm64\` with each subsystem on its own \`CONFIG_*\`; add DT binding compilation validation (\`dtbs_check\` if installed), initramfs first-boot smoke test; enable hardware node only when resource graph complete.
6. **Hardware acceptance:** collect log and state probes before and after, preserve EFS/MODEM/SYSTEM/VENDOR/USERDATA; never write to unsafe PMIC, UFS boot partitions, or calibration without validated driver.
7. **OneUI8 gate:** compare driver HAL sysfs, ioctls, service names and vendor manifest with working V12R5T; porting \`ANDROID_BINDER_IPC\` alone never enables One UI.

### Source inventory baseline

P5 \`V12R5T-DRIVER-MIGRATION.csv\` enumerated 7092 files across selected device subsystem directories; 4239 did not have an identical path in upstream 5.10. These are **file-counts, NOT 4239 independent drivers or missing 4239 functions**. Major groups (missing path): Mali 1586, camera 733, radios 1055, charger/power 176, display 129, UFS/PHY 76. Exact compatibility must be determined at **source/API + bind/test** level.

### Known blockers that should change priority

- **Current R1/R2 static splash:** before porting all drivers, prove G0. The barebox S8 patch highlights that S-Boot may supply rewritten DT in \`x0\` and have a limited stack. A 40MiB \`ANDROID!\` BOOT signature and passing CI do NOT prove the loader executes.
- **UFS/PMIC are cyclic dependencies:** controller needs clocks and rails; PMIC transport may depend on proprietary ACPM/firmware mailbox. Port read-only PMIC platform first; defer UFS enable until dependencies.
- **Display/graphics are coupled:** DECON, panel, IOMMU, ION heaps, Mali and HWC must agree on memory descriptors. Copying \`decon_core.c\` alone will not show Android UI.
- **Android Common Kernel choice:** upstream 5.10.262 is useful for minimal bring-up; for Android 16 integration evaluate \`android13-5.10\` ACK, but do not pretend a raw GKI drop-in will work with vendor 4.4 drivers/old bootloader.
- **Power/offline charging:** P2G-R2 does not include Samsung LPM; TWRP 4.4 reported charging at 62% and USB online, proving only original TWRP charge path.

## Repo safety

Use \`experimental/\` branches; do not merge with stable V12R5T. No new flashable kernel is generated by this document or its metadata tooling. Never overwrite original V12R5T BOOT backup or Samsung CP/EFS. All claims must be tied to built source and real-device logs.
