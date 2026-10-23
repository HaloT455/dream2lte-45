#!/usr/bin/env python3
"""Read-only cross-repository acceptance gate for S8+ Android 16.

Checks R16 modem Kconfig against the owner's working boot IKCONFIG, and
checks the matching Camera/Video6 vendor tree. DOES NOT establish bootability,
SIM registration or camera usability on a real phone.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

KERNEL_REQUIRED = {
    "CONFIG_SOC_EXYNOS8895": "y",
    "CONFIG_SEC_SIPC_MODEM_IF": "y",
    "CONFIG_SEC_MODEM_SS310AP": "y",
    "CONFIG_UMTS_MODEM_SS310AP": "y",
    "CONFIG_LINK_DEVICE_SHMEM": "y",
    "CONFIG_LINK_DEVICE_NAPI": "y",
    "CONFIG_SHM_IPC": "y",
    "CONFIG_MODEM_IF_QOS": "y",
    "CONFIG_EROFS_FS": "y",
    "CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYSTEP": "y",
}
# Verified by extracting IKCONFIG from user's SIM-working boot.img, Oct 23.
REFERENCE_MODEM_CONFIG = {
    "CONFIG_SEC_SIPC_MODEM_IF": "y",
    "CONFIG_SEC_MODEM_SS310AP": "y",
    "CONFIG_UMTS_MODEM_SS310AP": "y",
    "CONFIG_LINK_DEVICE_SHMEM": "y",
    "CONFIG_LINK_DEVICE_NAPI": "y",
    "CONFIG_SHM_IPC": "y",
    "CONFIG_MODEM_IF_QOS": "y",
    "CONFIG_EROFS_FS": "y",
}
REFERENCE_BOOT_SHA256 = "9012313ab3d8b2e15fe00871da4872d4d09f7068211b36604eede6fe138c646b"
REFERENCE_DTB_SHA256 = "ad861356479173627635f65a80b23b04697f8dcca509f1377804a1ec10eaf818"
CAMERA_TAGS = ("PREVIEW_TAG", "PICTURE_TAG", "VIDEO_TAG")
RIL_INIT = "etc/init/init.vendor.rilcommon.rc"


def kconfig(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        if raw.startswith("CONFIG_") and "=" in raw:
            name, value = raw.split("=", 1)
            out[name] = value
        elif raw.startswith("# CONFIG_") and raw.endswith(" is not set"):
            out[raw[2:].split(" ", 1)[0]] = "n"
    return out


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def boot_header(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 2048 or data[:8] != b"ANDROID!":
        raise ValueError("Not an Android boot image v0 reference")
    ksize, _kaddr, rsize, _raddr, second, _saddr, _tags, page, dsize, _unused = struct.unpack_from("<10I", data, 8)
    if not 2048 <= page <= 16384 or (page & (page - 1)):
        raise ValueError("Invalid boot page alignment")
    def align(n):
        return (n + page - 1) // page * page
    roff = page + align(ksize)
    doff = roff + align(rsize) + align(second)
    if doff + dsize > len(data):
        raise ValueError("Truncated boot image reference")
    ramdisk = data[roff:roff + rsize]
    dtb = data[doff:doff + dsize]
    plain = gzip.decompress(ramdisk) if ramdisk.startswith(b"\x1f\x8b") else ramdisk
    commandline = data[64:576].split(b"\x00", 1)[0].decode("ascii", "replace")
    return {
        "sha256": sha(data), "dtb_sha256": sha(dtb), "cmdline": commandline,
        "ramdisk_legacy_hmp": b"dh2_fastlane" in plain or b"interactive/hispeed_freq" in plain,
        "ramdisk_has_cpio": b"070701" in plain[:32] or b"070702" in plain[:32],
    }


def audit(kernel: Path, vendor: Path, reference_boot: Path | None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    cfg = kconfig(kernel / "arch/arm64/configs/exynos8895-dream2lte_defconfig")
    for key, value in KERNEL_REQUIRED.items():
        if cfg.get(key) != value:
            errors.append(f"Kernel {key}: got {cfg.get(key)!r}, expected {value!r}")
    for key, value in REFERENCE_MODEM_CONFIG.items():
        if cfg.get(key) != value:
            errors.append(f"Reference modem mismatch: {key}")
    props = (vendor / "vendor/build.prop").read_text()
    expected = ("ro.product.vendor.device=dream2lte", "ro.radio.noril=no",
                "ro.telephony.default_network=9,9", "ro.vendor.sec.radio.def_network=9")
    lines = props.splitlines()
    for s in expected:
        count = lines.count(s)
        # Historical Samsung Test7 repeats some immutable properties with the
        # same value. Duplicates alone are not regressions; conflicts are.
        if count < 1 or (s == "ro.telephony.default_network=9,9" and count != 1):
            errors.append(f"Vendor property missing/ambiguous: {s}")
        key = s.split("=", 1)[0] + "="
        if any(row.startswith(key) and row != s for row in lines):
            errors.append(f"Conflicting vendor value: {key[:-1]}")
    rc = (vendor / "vendor" / RIL_INIT).read_text()
    if "exec_start network_config" not in rc or "service network_config" not in rc:
        errors.append("Samsung network_config missing")
    if "setprop ro.telephony.default_network ${ro.vendor.radio.default_network}" in rc:
        warnings.append("Late ro.telephony.default_network setprop is source-matched but may be rejected as read-only on Android 16")
    for file in (
        "vendor/bin/hw/rild", "vendor/bin/secril_config_svc",
        "vendor/lib64/libsec-ril.so", "vendor/lib64/libril_sem.so",
        "vendor/etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml",
        "vendor/etc/vintf/manifest/vendor.samsung.hardware.sehradio_manifest_2_33.xml",
        "vendor/lib/hw/camera.universal8895.so", "vendor/lib64/hw/camera.universal8895.so",
    ):
        if not (vendor / file).is_file():
            errors.append("Required native component missing: " + file)
    camera = (vendor / "tools/native_camera/alice_preview_bridge.c").read_text()
    if not all(x in camera for x in CAMERA_TAGS) or "VIDEO_FIELDS 6" not in camera:
        errors.append("Camera/Video6 metadata bridge regression")
    if "SUPPORT_SCENE_OPTIMIZER" not in (vendor / "vendor/etc/alice-test7/camera-feature.xml").read_text():
        errors.append("Camera feature XML missing")
    boot = None
    if reference_boot:
        boot = boot_header(reference_boot)
        if boot["sha256"] != REFERENCE_BOOT_SHA256:
            errors.append("Reference boot SHA-256 mismatch")
        if boot["dtb_sha256"] != REFERENCE_DTB_SHA256:
            errors.append("Reference DTB SHA-256 mismatch")
        if "dream2lte" not in boot["cmdline"] or "samsungexynos8895" not in boot["cmdline"]:
            errors.append("Reference boot machine mismatch")
        if boot["ramdisk_legacy_hmp"]:
            warnings.append("Reference ramdisk uses obsolete HMP/interactive/DH2; do NOT repack it unchanged with R16 EnergyStep")
    return {
        "pair_id": "ALICE-S8P-A16-R16-SIMCAM-20261023",
        "static_contract": "PASS" if not errors else "FAIL",
        "kernel_governor": "EnergyStep", "reference_governor": "interactive",
        "reference_modem_symbols_compared": len(REFERENCE_MODEM_CONFIG),
        "reference_boot": boot, "errors": errors, "warnings": warnings,
        "device_boot_verified": False, "two_sim_registered_verified": False,
        "camera_recording_verified_by_ci": False, "flash_ready": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--vendor-root", required=True, type=Path)
    parser.add_argument("--reference-boot", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.kernel_root, args.vendor_root, args.reference_boot)
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    print(output)
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
