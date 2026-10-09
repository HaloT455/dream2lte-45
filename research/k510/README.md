# Alice K510 / dream2lte — Port Research P0 (NOT FLASHABLE)

**Target:** Samsung Galaxy S8+ SM-G955F (`dream2lte`), Exynos 8895 rev05, Android 16 vendor.
**Known-good baseline:** branch `v12` and booting Alice V12R5T Linux 4.4.302.
**New independent base:** Linux stable **v5.10.262** from `gregkh/linux`.

> IMPORTANT: The repository's `Makefile` in this research branch **still describes Linux 4.4**, because this branch was forked from `v12` for documentation and workflow reuse. The actual 5.10 source is fetched into a **separate directory** by `bootstrap.sh`. None of the files in this branch are a bootable 5.10 device port. DO NOT flash the generic ARM64 image.

## Verified references

- Samsung Galaxy A21s / Exynos 850 uses Android kernel 4.19 (LineageOS).
- Exynos 1280 uses an Android 5.10 downstream branch, but its device drivers are NOT drop-in compatible.
- Minimal Exynos 8895 mainline SoC + dreamlte patches were posted in September 2024; support includes CPU, pinctrl, GPIO, simple-framebuffer and pstore, enabling an initramfs shell with an appropriate bootloader/shim.
- S8+ needs distinct `dream2lte` device tree, memory reservations, regulator/display/storage/USB definitions and vendor compatibility validation.

## P0 deliverables (this commit)

- `research/k510/bootstrap.sh`: clone upstream v5.10.262 separately and optionally build a **generic ARM64 smoke-test Image**.
- `research/k510/driver-audit.sh`: inventory downstream device-tree and source layout, reporting port blockers.
- `.github/workflows/k510-source-smoke.yml`: compile 5.10 generic ARM64 from a verified tag in CI, archive Image labelled NOT_FLASHABLE.

## Local use on Zorin OS (no device writes)

```bash
sudo apt update
sudo apt install -y git make gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu \
  bc bison flex libssl-dev libelf-dev build-essential
# Prefer an external SSD with >=20 GB free:
export K510_WORKDIR=/path/on/external-ssd/alice-k510
bash research/k510/bootstrap.sh --fetch
bash research/k510/bootstrap.sh --build
bash research/k510/driver-audit.sh . "$K510_WORKDIR/linux-5.10.262"
```

The output `out/arch/arm64/boot/Image` is a **generic upstream build only**. Do **NOT** use Odin, TWRP, fastboot, dd or AnyKernel to flash this image.

## Port gates (must be demonstrated before any flashable file)

1. P0: upstream v5.10.262 source and ARM64 compilation reproducible; no claims of S8+ boot.
2. P1: cherry-pick/adapt Exynos8895 SoC support to 5.10, validate DTS compilation and correct `dream2lte` DT, clocks, reserved memory.
3. P2: isolated early-boot validation with recovery route; serial/pstore diagnostics and Samsung s-boot/uniLoader compatibility.
4. P3: storage, USB, display, touch, thermal and power management; persistent crash logs.
5. P4: GPU, camera, radio/modem, Wi-Fi, Bluetooth, audio, Android vendor/HAL, SELinux and KernelSU.
6. P5: Android 16 smoke-test and only then offer a clearly identified experimental boot image.

## Device guardrails

- SM-G955F / Exynos8895 **only**. Reported `ro.product.model=SM-S901B` is a ROM spoof; hardware is verified via `/proc/device-tree/model`.
- Do not transplant Exynos850 DTB, drivers, boot partition images or modem blobs.
- Leave the running 4.4.302 kernel and its boot image untouched.
- Backup known-good `boot.img` and recovery method before future P2 boot experiments.
- A compile success is not a boot-success claim.

## References

- https://github.com/LineageOS/lineage_wiki/blob/main/_data/devices/a21s.yml
- https://github.com/gregkh/linux/tree/v5.10.262
- https://lists.openwall.net/linux-kernel/2024/09/09/753
- https://github.com/torvalds/linux/blob/master/arch/arm64/boot/dts/exynos/exynos8895-dreamlte.dts
