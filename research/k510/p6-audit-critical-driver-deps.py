#!/usr/bin/env python3
"""Deterministic P6 pre-port audit of critical V12R5T hardware sources.

NO source copying, NO Kconfig enabling, NO writing images, NO device IO.
Reports *file-level* include availability and Linux 5.10 target counterpart;
this is not proof of source/API compatibility.
"""
import argparse
import csv
import json
import re
import subprocess
from pathlib import Path

PIN = "3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3"
DRIVERS = [
    ("pmic", "drivers/mfd/s2mps17_core.c", "", "Samsung ACPM, IRQ domain and MFD device registration"),
    ("pmic", "drivers/regulator/s2mps17.c", "", "regulator_desc, Samsung PMIC GPIO and voltage selectors"),
    ("pmic", "drivers/mfd/max77865.c", "", "I2C/MFD IRQ and max77865-private header"),
    ("charging", "drivers/battery_v2/max77865_charger.c", "", "power_supply API, Samsung battery notifier, usb_notify"),
    ("charging", "drivers/battery_v2/max77865_fuelgauge.c", "", "power_supply API, regmap and fuel-gauge calibration"),
    ("ufs", "drivers/scsi/ufs/ufs-exynos.c", "drivers/scsi/ufs/ufs-exynos.c", "Same filename is NOT compatible: Exynos8895 PHY, PM, UNIPRO and private UFS APIs"),
    ("display", "drivers/video/fbdev/exynos/dpu/decon_core.c", "", "ION / DMA-BUF, EXYNOS IOVMM, FBDEV and display clocks"),
    ("mali", "drivers/gpu/arm/tMIx/Kconfig", "", "Proprietary Mali-G71 Bifrost r19p0 + matching userspace ioctl ABI"),
    ("camera", "drivers/media/platform/exynos/fimc-is2/Kconfig", "", "FIMC-IS2 ISP firmware, SMMU, V4L2 and media graph"),
]
INCLUDE_RX = re.compile(r'^\s*#\s*include\s*[<"]([^">]+)[">]', re.M)

def g(*args):
    return subprocess.check_output(["git", *map(str, args)], text=True, stderr=subprocess.PIPE)

def donor_read(donor, path):
    return g("-C", donor, "show", f"{PIN}:{path}")

def present_target(target, group, path, header):
    # A missing *identical* header path is only an indication of work needed,
    # not an indication that Linux 5.10 lacks equivalent functional APIs.
    options = [
        target / "include" / header,
        target / "arch/arm64/include" / header,
        target / Path(path).parent / header,
        target / "drivers" / header,
    ]
    return any(x.is_file() for x in options)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--donor-repo", type=Path, required=True)
    ap.add_argument("--linux-510", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    arg = ap.parse_args()
    if g("-C", arg.donor_repo, "rev-parse", "--verify", f"{PIN}^{{commit}}").strip() != PIN:
        raise SystemExit("Donor commit is not pinned V12R5T source")
    version = subprocess.check_output(["make", "-s", "-C", str(arg.linux_510), "kernelversion"], text=True).strip()
    if version != "5.10.262":
        raise SystemExit(f"Expected genuine Linux 5.10.262, got {version}")
    arg.out.mkdir(parents=True, exist_ok=True)
    result = []
    for group, path, target_reference, barrier in DRIVERS:
        donor = donor_read(arg.donor_repo, path)
        includes = sorted(set(INCLUDE_RX.findall(donor)))
        unresolved = [h for h in includes if not present_target(arg.linux_510, group, path, h)]
        result.append(dict(
            group=group,
            donor_path=path,
            donor_bytes=len(donor.encode()),
            upstream_counterpart=target_reference,
            upstream_counterpart_present=bool(target_reference and (arg.linux_510 / target_reference).is_file()),
            donor_header_count=len(includes),
            exact_include_paths_not_found=len(unresolved),
            missing_include_paths=unresolved,
            main_api_barrier=barrier,
            state="REQUIRES_API_AND_BINDING_ADAPTATION",
        ))
    (arg.out/"P6-HARDWARE-PORT-READINESS.json").write_text(json.dumps({
        "warning": "This is a static dependency map, NOT complete driver port or runtime verification",
        "donor_pin": PIN,
        "target": version,
        "drivers": result,
    }, indent=2)+"\n")
    with (arg.out/"P6-HARDWARE-PORT-READINESS.csv").open("w", newline="") as fd:
        wr=csv.writer(fd)
        wr.writerow(["group", "donor_path", "bytes", "upstream_counterpart",
                     "upstream_exists", "includes", "missing_exact_include_paths", "API_barrier"])
        for x in result:
            wr.writerow([x["group"], x["donor_path"], x["donor_bytes"],
                         x["upstream_counterpart"], int(x["upstream_counterpart_present"]),
                         x["donor_header_count"], x["exact_include_paths_not_found"],
                         x["main_api_barrier"]])
    doc=["# P6 V12R5T driver readiness — compile-time triage", "",
         "Source: exact donor pinned commit. Target: unmodified Linux 5.10.262.",
         "Missing exact include paths do NOT prove that functionality is absent; upstream APIs may be relocated/renamed.", "",
         "| Driver group | Donor source | Matching upstream file | Missing exact include paths |",
         "|---|---|---|---:|"]
    for x in result:
        doc.append(f"| {x['group']} | \`{x['donor_path']}\` | {'Yes (API may differ)' if x['upstream_counterpart_present'] else 'No, vendor port'} | {x['exact_include_paths_not_found']} |")
    doc+=["", "### Per-driver blockers", ""]
    for x in result:
        doc.append(f"**{x['donor_path']}** — {x['main_api_barrier']}.")
        doc.append("Absent exact header paths: "+(", ".join("\`"+z+"\`" for z in x["missing_include_paths"]) or "none detected")+".")
        doc.append("")
    (arg.out/"P6-HARDWARE-PORT-READINESS.md").write_text("\n".join(doc)+"\n")
    print(json.dumps({"donor":PIN,"kernel":version,"analyzed":len(result),
                      "total_unresolved_exact_includes":sum(x["exact_include_paths_not_found"] for x in result)},indent=2))
    print("NO vendor hardware driver copied or enabled. NO BOOT image produced.")

if __name__=="__main__":
    main()
