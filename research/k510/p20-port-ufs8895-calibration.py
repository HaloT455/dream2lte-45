#!/usr/bin/env python3
"""Stage exact original Exynos8895 UFS calibration DATA into Linux 5.10.

One-to-one type/mode/register/value translation, preserving every donor row and
sequence. It does NOT execute hardware writes or register an incomplete
Exynos8895 driver. CI links the concrete C calibration tables into vmlinux.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PIN = "3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3"
KEYS = (
    "phy-init", "post-phy-init", "calib-of-pwm", "calib-of-hs-rate-a",
    "calib-of-hs-rate-b", "post-calib-of-hs-rate-a",
    "post-calib-of-hs-rate-b", "pre-clk-off", "post-clk-on",
    "lane1-sq-off",
)
TYPES = (
    "PHY_CFG_NONE", "PHY_PCS_COMN", "PHY_PCS_RXTX", "PHY_PMA_COMN",
    "PHY_PMA_TRSV", "PHY_PLL_WAIT", "PHY_CDR_WAIT",
    "UNIPRO_STD_MIB", "UNIPRO_DBG_MIB", "UNIPRO_DBG_APB",
    "PHY_PCS_RX", "PHY_PCS_TX", "PHY_PCS_RX_PRD", "PHY_PCS_TX_PRD",
    "UNIPRO_DBG_PRD", "PHY_PMA_TRSV_LANE1_SQ_OFF", "COMMON_WAIT",
)
MODE_BITS = (
    "PMD_PWM_G1_L1", "PMD_PWM_G1_L2", "PMD_PWM_G2_L1",
    "PMD_PWM_G2_L2", "PMD_PWM_G3_L1", "PMD_PWM_G3_L2",
    "PMD_PWM_G4_L1", "PMD_PWM_G4_L2", "PMD_PWM_G5_L1",
    "PMD_PWM_G5_L2", "PMD_HS_G1_L1", "PMD_HS_G1_L2",
    "PMD_HS_G2_L1", "PMD_HS_G2_L2", "PMD_HS_G3_L1",
    "PMD_HS_G3_L2",
)
EXPECTED = [31, 9, 20, 27, 27, 1, 1, 3, 3, 2]

def refuse(msg: str):
    raise SystemExit("P20 REFUSED: " + msg)

def original(donor: Path, path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(donor), "show", f"{PIN}:{path}"], text=True
    )

if len(sys.argv) != 4:
    refuse("Usage: p20-port-ufs8895-calibration.py DONOR_REPO LINUX510_TREE REPORT_DIR")
donor, tree, out = map(Path, sys.argv[1:])
out.mkdir(parents=True, exist_ok=True)
soc = original(donor, "arch/arm64/boot/dts/exynos/exynos8895.dtsi")
vendor_h = original(donor, "drivers/scsi/ufs/ufs-exynos.h")
start = soc.find("ufs@0x11120000 {")
end = soc.find("ufs_fixed_vcc:", start)
if start < 0 or end < start:
    refuse("can not identify original Exynos8895 UFS and VCC bounds")
node = soc[start:end]
if not all(("PHY_PMA_TRSV_ADDR(reg, lane)" in vendor_h,
            "((reg) + (0x140 * (lane)))" in vendor_h,
            "#define PMD_ALL" in vendor_h)):
    refuse("original Exynos8895 PHY lane ABI changed")
for typ in TYPES:
    if not re.search(r"\b" + typ + r"\b", vendor_h):
        refuse("donor missing type " + typ)
for bit in MODE_BITS:
    if not re.search(r"\b#define\s+" + bit + r"\b", vendor_h):
        refuse("donor missing mode " + bit)

clean = re.sub(r"/\*.*?\*/", "", node, flags=re.S)
clean = re.sub(r"//[^\n]*", "", clean)
records = []
all_count = 0
for idx, (key, expected) in enumerate(zip(KEYS, EXPECTED)):
    pat = r"(?m)^\s*" + re.escape(key) + r"\s*=\s*(.*?);"
    match = re.search(pat, clean, re.S)
    if not match:
        refuse("missing calibration table " + key)
    raw = match.group(1)
    rows = [row.strip() for row in re.findall(r"<(.*?)>\s*(?:,|$)", raw, flags=re.S)]
    if not rows:
        refuse("no data for " + key)
    sentinel = rows.pop()
    if not re.fullmatch(r"0\s+0\s+0\s+0", sentinel):
        refuse(f"missing four-zero terminator in {key}: {sentinel!r}")
    if len(rows) != expected:
        refuse(f"{key} count {len(rows)} != pinned original {expected}")
    parsed = []
    for row in rows:
        m = re.fullmatch(
            r"(\w+)\s+(.+?)\s+(\(?PMD_[A-Z0-9_|]+\)?)\s+([A-Z0-9_]+)",
            re.sub(r"\s+", " ", row),
        )
        if not m:
            refuse("unparseable calibration row " + key + " " + row)
        addr, val, flag, typ = m.groups()
        if typ not in TYPES[1:]:
            refuse("unknown MMIO operation " + typ)
        if not re.fullmatch(r"(?:0x[0-9a-fA-F]+|[0-9]+)", addr):
            refuse("unexpected nonnumeric register address: " + addr)
        if not re.fullmatch(r"[a-zA-Z0-9_\s()/+*|&<>-]+", val):
            refuse("unexpected value expression " + val)
        if re.search(r"\b[A-Z_][A-Z0-9_]*\b", val):
            refuse("value depends on unknown macro " + val)
        bare = flag.strip("()").split("|")
        if not all(f in MODE_BITS or f in ("PMD_ALL", "PMD_PWM", "PMD_HS")
                   for f in bare):
            refuse("unrecognized lane/power selector " + flag)
        parsed.append((addr, val, flag, typ))
    all_count += len(parsed)
    records.append((key, parsed, hashlib.sha256(raw.encode()).hexdigest()))

if all_count != 124:
    refuse(f"original calibration must have exactly 124 entries, found {all_count}")

target_dir = tree / "drivers/scsi/ufs"
if not (target_dir / "ufs-exynos.c").exists():
    refuse("native Linux 5.10 host source not found")
hpath = target_dir / "alice-ufs8895-calibration.h"
cpath = target_dir / "alice-ufs8895-calibration.c"
if hpath.exists() or cpath.exists():
    refuse("will not overwrite previously staged calibration data")
header = r"""/* SPDX-License-Identifier: GPL-2.0 */
/* Original Exynos8895 Samsung calibration TRANSLATED DATA ONLY.
 * No MMIO execution, no platform compatible registration, no flash.
 */
#ifndef _ALICE_UFS8895_CALIBRATION_H_
#define _ALICE_UFS8895_CALIBRATION_H_
#include <linux/types.h>

enum alice_ufs8895_space {
"""
for i,t in enumerate(TYPES):
    header += f"\tALICE_8895_{t} = {i},\n"
header += """};

struct alice_ufs8895_cal_entry {
    u32 address;
    u32 value;
    u32 power_mode_mask;
    enum alice_ufs8895_space space;
};

struct alice_ufs8895_cal_table {
    const char *original_dts_property;
    const struct alice_ufs8895_cal_entry *entries;
    u32 count;
};

/* DATA access only; caller MUST NOT apply to hardware until reviewed. */
const struct alice_ufs8895_cal_table *alice_ufs8895_get_calibration(unsigned int phase);
#define ALICE_UFS8895_CAL_PHASE_COUNT 10
#define ALICE_UFS8895_PHY_LANE_STRIDE 0x140U
#endif
"""
source = '/* SPDX-License-Identifier: GPL-2.0 */\n#include <linux/kernel.h>\n#include "alice-ufs8895-calibration.h"\n\n'
source += "/* Exact power-mask bit positions copied from the pinned Samsung donor ABI. */\n"
for i,n in enumerate(MODE_BITS):
    source += f"#define {n} (1U << {i})\n"
source += "#define PMD_ALL (PMD_HS_G3_L2 - 1U)\n"
source += "#define PMD_PWM (PMD_PWM_G4_L2 - 1U)\n"
source += "#define PMD_HS (PMD_ALL ^ PMD_PWM)\n\n"
for idx,(key,parsed,digest) in enumerate(records):
    source += f"/* Original DT {key}, {len(parsed)} rows, raw SHA256: {digest} */\n"
    source += f"static const struct alice_ufs8895_cal_entry alice_ufs8895_phase_{idx}[] = {{\n"
    for addr,val,flag,typ in parsed:
        source += f"    {{ {addr}, {val}, {flag}, ALICE_8895_{typ} }},\n"
    source += "};\n\n"
source += "static const struct alice_ufs8895_cal_table alice_ufs8895_tables[] = {\n"
for idx,(key,parsed,digest) in enumerate(records):
    source += f'    {{ "{key}", alice_ufs8895_phase_{idx}, ARRAY_SIZE(alice_ufs8895_phase_{idx}) }},\n'
source += "};\n\n"
source += """const struct alice_ufs8895_cal_table *
alice_ufs8895_get_calibration(unsigned int phase)
{
    if (phase >= ARRAY_SIZE(alice_ufs8895_tables))
        return NULL;
    return &alice_ufs8895_tables[phase];
}
"""
hpath.write_text(header)
cpath.write_text(source)
main_kbuild = target_dir / "Makefile"
mk = main_kbuild.read_text()
if "alice-ufs8895-calibration.o" in mk:
    refuse("already registered in Kbuild")
main_kbuild.write_text(mk + "\n# P20 disposable CI DATA-ONLY 8895 calibration link gate (never ship)\nobj-y += alice-ufs8895-calibration.o\n")
report = {
    "donor_pin": PIN,
    "linux_kernel": "v5.10.262",
    "original_dts_path": "arch/arm64/boot/dts/exynos/exynos8895.dtsi",
    "table_count": len(records),
    "entry_count": all_count,
    "phy_lane_stride_original": "0x140",
    "registered_driver": False,
    "writes_mmio": False,
    "executable_boot": False,
    "tables": [
        {"phase": idx, "property": key, "entries":len(rows), "raw_dts_sha256":digest}
        for idx,(key,rows,digest) in enumerate(records)
    ],
    "generated_c_sha256": hashlib.sha256(source.encode()).hexdigest(),
}
(out / "p20-calibration-port.json").write_text(json.dumps(report, indent=2) + "\n")
print("P20: 124/124 original Exynos8895 calibration entries translated into real Linux 5.10 C arrays.")
print("P20: detected PHY TRSV LANE STRIDE = 0x140 (not generic Exynos7 0x30).")
print("P20: separate host/platform driver callback and secure storage port remains UNIMPLEMENTED.")
print("P20: no MMIO, no probe, no boot, no flash.")
