#!/usr/bin/env python3
"""P18 pinned Exynos8895 donor DT/ACPM/S2MPS17/UFS dependency audit.
Reads files only; reports *unmet* hardware boot gates; no kernel binary or DT edits.
"""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PIN = "3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3"
if len(sys.argv) != 4:
    sys.exit("Usage: p18-audit-hardware.py DONOR_GIT LINUX510_TREE OUTPUT_DIR")
donor, kernel, output = (Path(x) for x in sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)

def original(path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(donor), "show", f"{PIN}:{path}"]
    ).decode("utf-8")

def require(condition: bool, msg: str) -> None:
    if not condition:
        raise SystemExit("P18 REFUSED: " + msg)

def get_node(data: str, label: str) -> str:
    # The selected node starts at label. Find its matched braces, avoiding
    # bleed into unrelated sibling nodes. This is a narrowly scoped audit,
    # NOT a full DT grammar parser or an executable DTS conversion.
    rx = re.search(label + r"\s*\{", data)
    require(bool(rx), f"missing DT node {label!r}")
    start = rx.end()
    nesting = 1
    for idx in range(start, len(data)):
        if data[idx] == "{":
            nesting += 1
        elif data[idx] == "}":
            nesting -= 1
            if not nesting:
                return data[start:idx]
    raise SystemExit("P18 REFUSED: unclosed DT node " + label)

def get_table(src: str, key: str) -> tuple[int, str]:
    result = re.search(
        r"(?m)^\s*" + re.escape(key) + r"\s*=\s*(.*?);", src, re.S
    )
    require(bool(result), f"missing exact donor calibration property: {key}")
    text = result.group(1)
    values = [s.strip() for s in re.findall(r"<([^>]+)>", text, re.S)]
    require(len(values) > 1, f"empty calibration property {key}")
    require(any(re.fullmatch(r"\s*0\s+0\s+0\s+0\s*", v) for v in values),
            f"calibration table {key} lacks sentinel")
    return len(values) - 1, hashlib.sha256(text.encode()).hexdigest()

soc = original("arch/arm64/boot/dts/exynos/exynos8895.dtsi")
board = original("arch/arm64/boot/dts/exynos/exynos8895-dream2lte_common.dtsi")
donor_driver = original("drivers/scsi/ufs/ufs-exynos.c")
main_dts_path = kernel / "arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
require(main_dts_path.is_file(), "staged Linux 5.10 dream2lte DTS missing")
main_dts = main_dts_path.read_text()
vendor_ufs = get_node(soc, r"ufs@0x11120000")
vendor_acpm = get_node(soc, r"\bacpm")
vendor_ipc = get_node(soc, r"\bacpm_ipc")
vendor_pmic = get_node(board, r"s2mps17mfd@00")
v510_ufs = get_node(main_dts, r"alice_ufs_embd:\s*ufs@11120000")
require(bool(re.search(r'status\s*=\s*"disabled"\s*;', v510_ufs)),
        "Linux 5.10 UFS must remain disabled")
require('i2c-speedy-address' in vendor_pmic,
        "donor PMIC Speedy dependency cannot be silently ignored")
require("acpm-ipc-channel = <2>" in vendor_pmic,
        "donor PMIC ACPM IPC channel 2 not found")
require('compatible = "samsung,exynos-acpm-ipc"' in vendor_ipc,
        "donor ACPM mailbox binding missing")
require("initdata-base = <0x2850>" in vendor_ipc,
        "ACPM firmware init data layout mismatch")
require("ufs-phy {" in vendor_ufs and "ufs-tcxo-sel {" in vendor_ufs,
        "vendor UFS PHY / TCXO subnodes missing")
require("vcc-supply = <&ufs_fixed_vcc>" in vendor_ufs,
        "vendor UFS power supply reference missing")
require('compatible ="samsung,exynos-ufs"' in vendor_ufs,
        "vendor compatible binding changed unexpectedly")
require('compatible = "samsung,exynos7-ufs"' in v510_ufs,
        "native 5.10 experimental UFS host binding unexpected")
require('ufs_fixed_vcc: fixedregulator@0' in soc,
        "donor UFS fixed-VCC regulator absent")

tables = {}
for key in (
    "phy-init", "post-phy-init", "calib-of-pwm",
    "calib-of-hs-rate-a", "calib-of-hs-rate-b",
    "post-calib-of-hs-rate-a", "post-calib-of-hs-rate-b",
    "pre-clk-off", "post-clk-on", "lane1-sq-off",
):
    n, sha = get_table(vendor_ufs, key)
    tables[key] = {"entries_excluding_terminator": n, "sha256": sha}

donor_clock_names = re.search(
    r"clock-names\s*=\s*(.*?);", vendor_ufs, re.S
)
require(bool(donor_clock_names), "original UFS clock-names unavailable")
clock_names = re.findall(r'"([^"]+)"', donor_clock_names.group(1))
require("GATE_UFS_EMBD" in clock_names and "UFS_EMBD" in clock_names,
        "original UFS clocks not recognized")
donor_regs = re.search(r"reg\s*=\s*(.*?);", vendor_ufs, re.S)
require(bool(donor_regs), "original UFS registers missing")
ips = ["0x11120000", "0x11121100", "0x11110000", "0x11130000"]
require(all(ip in donor_regs.group(1) for ip in ips),
        "original UFS register windows mismatch")

report = {
    "stage": "P18_STATIC_DEPENDENCY_AUDIT_ONLY",
    "donor_revision": PIN,
    "donor_paths": [
        "arch/arm64/boot/dts/exynos/exynos8895.dtsi",
        "arch/arm64/boot/dts/exynos/exynos8895-dream2lte_common.dtsi",
        "drivers/scsi/ufs/ufs-exynos.c",
        "drivers/scsi/ufs/ufs-exynos.h",
    ],
    "ufs": {
        "vendor_compatible": "samsung,exynos-ufs",
        "native_5_10_compatible": "samsung,exynos7-ufs",
        "native_5_10_status": "disabled",
        "vendor_clock_names": clock_names,
        "vendor_register_windows": ips,
        "vendor_vcc_supply": "ufs_fixed_vcc",
        "vendor_phy_tuning": tables,
        "vendor_driver_bytes": len(donor_driver.encode()),
        "portability_verified": False,
    },
    "acpm_pmic": {
        "vendor_mailbox_register_bases": ["0x16440000", "0x16500000"],
        "vendor_mailbox_irq_spi": 39,
        "vendor_firmware_initdata_base": "0x2850",
        "vendor_pmic_model": "s2mps17",
        "vendor_pmic_ipc_channel": 2,
        "vendor_pmic_transport": "Samsung Speedy + ACPM",
        "native_5_10_speedy_runtime_implemented": False,
        "mailbox_runtime_validated": False,
    },
    "gates": {
        "p17_vmlinux_link": "PASS in previous CI only",
        "donor_ufs_dts_calibration_extracted": "PASS",
        "acpm_mailbox_and_pmic_dependencies_identified": "PASS",
        "ufs_controller_api_port": "UNVERIFIED",
        "ufs_phy_unipro_specific_calibration_port": "UNVERIFIED",
        "power_rail_and_speedy_startup": "UNVERIFIED",
        "safe_runtime_readonly_ufs_enumeration": "NOT_TESTED",
        "android_first_stage_init": "NOT_TESTED",
    },
    "ready_to_flash": False,
}
require("0x16440000" in vendor_ipc and "0x16500000" in vendor_ipc,
        "ACPM mailbox address mismatch")
require("interrupts = <0 39 0>" in vendor_ipc,
        "ACPM IPC interrupt mismatch")
(output / "p18-hardware-audit.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
md = [
    "# P18 Hardware Dependency Audit – Original Exynos8895 versus Linux 5.10",
    "",
    f"Pinned V12R5T donor: \`{PIN}\`",
    "",
    "## Verified facts from donor DTS",
    "",
    "- Original UFS controller binding: \`samsung,exynos-ufs\`; mainline staging has \`samsung,exynos7-ufs\`, **not equivalent without porting**.",
    f"- Original UFS clock names: \`{', '.join(clock_names)}\`.",
    "- UFS four HCI/vendor/UniPro/protector register windows: \`" + "\`, \`".join(ips) + "\`.",
    "- Original UFS supply references \`ufs_fixed_vcc\`; original PHY + SYSREG + TCXO nodes are present.",
    "- PMIC S2MPS17 uses ACPM IPC channel 2 and vendor Samsung Speedy transport.",
    "- ACPM mailbox AP2APM base: 0x16440000; firmware SRAM base: 0x16500000; IRQ SPI39; initdata-base 0x2850.",
    "- Linux 5.10 experiment has UFS DT **disabled**. No physical UFS probe or power writes permitted.",
    "",
    "## Extracted PHY calibration tables (do not apply without register semantics)",
    "",
    "| Donor DT property | Entries | Original table SHA256 |",
    "|---|---:|---|",
]
md.extend(f"| \`{k}\` | {v['entries_excluding_terminator']} | \`{v['sha256']}\` |"
          for k, v in tables.items())
md += [
    "",
    "## Hardware gates still BLOCKED",
    "",
    "- Exact Exynos8895 M-PHY/UniPro tuning vs Linux 5.10 PHY driver semantics.",
    "- ACPM mailbox firmware/SRAM ordering, release/reboot and IPC timeout/error behavior.",
    "- Samsung Speedy controller and S2MPS17 rail/DVS/IRQ ownership; **never fall back silently**.",
    "- Device-tree clocks, supplies and pinctrl graph, UFS read-only enumeration, mount and Android init.",
    "",
    "**P18 is a compile/DT research audit. No \`boot.img\`, firmware load, regulator write or UFS hardware probe; NOT FLASHABLE.**",
]
(output / "P18-HARDWARE-AUDIT.md").write_text("\n".join(md) + "\n")
print("P18 donor ACPM + S2MPS17 + Exynos8895 UFS dependencies identified; no driver runtime claim.")
for k,v in tables.items():
    print(f"P18 donor {k}: {v['entries_excluding_terminator']} entries")
print("P18 safety gate: ready_to_flash=false; experimental Linux 5.10 UFS remains disabled.")
