#!/usr/bin/env python3
"""P5 V12R5T -> Linux 5.10 *source inventory*, not a compatibility claim.

Pin the last known-working V12R5T source revision; preserve exact kernel 4.4
blob IDs. A matching file path in 5.10 DOES NOT mean binary/API compatibility.
Never inject uncompiled vendor 4.4 modules into an Android 16 system.
"""
import argparse
import collections
import csv
import json
from pathlib import Path
import subprocess

V12R5T_PIN = "3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3"
GROUPS = (
    ("ufs_storage", ("drivers/scsi/ufs/", "drivers/phy/", "drivers/crypto/fmp/")),
    ("power_pmic_battery", ("drivers/battery/", "drivers/battery_v2/", "drivers/mfd/",
                            "drivers/regulator/", "drivers/power/")),
    ("display", ("drivers/video/fbdev/exynos/", "drivers/gpu/drm/exynos/",
                  "drivers/gpu/drm/panel/")),
    ("mali_gpu", ("drivers/gpu/arm/",)),
    ("camera_isp", ("drivers/media/platform/exynos/", "drivers/media/i2c/")),
    ("radio_wireless", ("drivers/net/wireless/", "drivers/bluetooth/", "drivers/nfc/")),
    ("sound", ("sound/soc/samsung/",)),
    ("soc_clock_pinctrl", ("drivers/soc/samsung/", "drivers/clk/samsung/",
                           "drivers/pinctrl/samsung/", "drivers/thermal/samsung/")),
    ("usb_typec", ("drivers/usb/",)),
    ("android_core", ("drivers/android/", "drivers/staging/android/", "fs/erofs/", "fs/f2fs/")),
    ("input_sensors", ("drivers/input/", "drivers/iio/", "drivers/sensors/", "drivers/leds/")),
)

def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--donor-repo", type=Path, required=True)
    ap.add_argument("--linux-510", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if git(a.donor_repo, "rev-parse", "--verify", V12R5T_PIN + "^{commit}").strip() != V12R5T_PIN:
        raise SystemExit("V12R5T exact donor revision is unavailable")
    if not (a.linux_510/"drivers").is_dir():
        raise SystemExit("Not a Linux 5.10 source directory")
    if "5.10.262" not in (a.linux_510/"Makefile").read_text()[:1200] and \
       subprocess.check_output(["make", "-s", "-C", str(a.linux_510), "kernelversion"], text=True).strip() != "5.10.262":
        raise SystemExit("Expected genuine Linux 5.10.262")
    lines = git(a.donor_repo, "ls-tree", "-r", V12R5T_PIN, "--", "drivers", "sound/soc/samsung", "fs/erofs", "fs/f2fs").splitlines()
    a.out.mkdir(parents=True, exist_ok=True)
    counts = collections.defaultdict(collections.Counter)
    paths = set()
    n = 0
    with (a.out/"V12R5T-DRIVER-MIGRATION.csv").open("w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["subsystem","v12r5t_kernel_4_4_path","v12r5t_git_blob_sha",
                     "linux_5_10_path_present","status"])
        for line in lines:
            meta, path = line.split("\t", 1)
            mode, ty, sha = meta.split()
            if ty != "blob" or not path.endswith((".c", ".h", ".S", "Kconfig", "Makefile", ".dts", ".dtsi")):
                continue
            group = next((name for name, pref in GROUPS if path.startswith(pref)), None)
            if not group:
                continue
            if path in paths:
                raise SystemExit("Duplicate source path: " + path)
            paths.add(path)
            n += 1
            exists = (a.linux_510/path).is_file()
            # Direct path equality does NOT establish ABI/API equivalence.
            status = "SAME_PATH_NOT_COMPATIBILITY_PROOF" if exists else "VENDOR_PORT_AND_DEPENDENCIES_REQUIRED"
            wr.writerow([group, path, sha, int(exists), status])
            counts[group]["total"] += 1
            counts[group]["upstream_path_only" if exists else "missing_from_510"] += 1
    for req in ("drivers/scsi/ufs/ufs-exynos.c",
                "drivers/battery_v2/max77865_charger.c",
                "drivers/battery_v2/max77865_fuelgauge.c",
                "drivers/gpu/arm/Kconfig",
                "drivers/video/fbdev/exynos/dpu/decon_core.c"):
        if req not in paths:
            raise SystemExit("Missing mandatory V12R5T device driver: " + req)
    result = {
        "status": "SOURCE_INVENTORY_ONLY_NEVER_ASSUME_ALL_DRIVERS_PORTED",
        "device": "SM-G955F Exynos8895",
        "v12r5t_pin": V12R5T_PIN,
        "target": "genuine Linux 5.10.262",
        "device_source_files_inventory": n,
        "groups": {k: dict(v) for k, v in sorted(counts.items())},
        "priority": [
            "P0 kernel boot handshake, UART, GIC, clocks, pinctrl, PSCI",
            "P1 UFS PHY/regulator/calibration (storage remains disabled until safe)",
            "P2 MAX77865 battery, fuel-gauge, S2MPS17 regulator and charger OFF",
            "P3 DECON+DSIM+AMOLED panel with exact hardware timings",
            "P4 ARM Mali Bifrost r19p0 and ION/DMABUF userspace bridge",
            "P5 Samsung camera FIMC-IS2 ISP + firmware (requires custom 5.10 driver)",
            "P6 modem, RIL, WiFi/BT/NFC, audio, fingerprint, sensors",
            "P7 Android 16 boot/init/SELinux/EROFS/F2FS userspace integration"
        ],
        "warning": "No hardware/vendor driver copied into active Linux 5.10 Kbuild by audit."
    }
    (a.out/"V12R5T-MIGRATION-SUMMARY.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print("V12R5T driver inventory completed; NOT a driver-port success claim.")

if __name__ == "__main__":
    main()
