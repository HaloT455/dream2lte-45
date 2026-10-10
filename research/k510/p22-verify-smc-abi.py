#!/usr/bin/env python3
"""Audit pinned Samsung Secure Monitor ABI before P22 AArch64 compilation.

No runtime SMC calls; do not treat Linux 5.10 Exynos7 NSSMU disabling
encryption as an acceptable replacement for Exynos8895 Samsung FMP.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

PIN = "3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3"
COMMANDS = {
    "SMC_CMD_FMP_SECURITY": 0xC2001810,
    "SMC_CMD_FMP_DISKENC": 0xC2001820,
    "SMC_CMD_SMU": 0xC2001830,
    "SMC_CMD_LOG": 0xC2001860,
    "ID_FMP_UFS_MMC": 0,
    "FMP_SMU_INIT": 0,
    "FMP_DESCTYPE_0": 0,
    "FMP_DESCTYPE_3": 3,
}
def require(cond, message):
    if not cond:
        raise SystemExit("P22 REFUSED: " + message)
def pinned(root, path):
    return subprocess.check_output(
        ["git", "-C", str(root), "show", f"{PIN}:{path}"], text=True
    )
if len(sys.argv) != 4:
    raise SystemExit("Usage: p22-verify-smc-abi.py REPO LINUX510 OUTPUT")
root, tree, output = map(Path, sys.argv[1:])
output.mkdir(exist_ok=True, parents=True)
header = pinned(root, "include/linux/smc.h")
asm = pinned(root, "arch/arm64/kernel/exynos-smc.S")
sw = pinned(root, "drivers/soc/samsung/exynos-smc.c")
ufs = pinned(root, "drivers/scsi/ufs/ufs-exynos.c")
fmp = pinned(root, "drivers/crypto/fmp/fmp_ufs.c")
native = (tree / "include/linux/arm-smccc.h").read_text()
exynos7 = (tree / "drivers/scsi/ufs/ufs-exynos.c").read_text()
p22 = (root / "research/k510/p22-ufs8895-secure.c").read_text()
p22h = (root / "research/k510/p22-ufs8895-secure.h").read_text()
for name, value in COMMANDS.items():
    m = re.search(r"(?m)^\s*#define\s+" + re.escape(name) +
                  r"\s+\(?\s*(0x[0-9a-fA-F]+|\d+)\s*\)?", header)
    require(m is not None, "donor SMC symbol missing: " + name)
    require(int(m.group(1), 0) == value, "donor ABI changed: " + name)
require(bool(re.search(r"(?s)ENTRY\(__exynos_smc\).*?dsb\s+sy\s*\n\s*smc\s+#0", asm)),
        "donor ARM64 SMC barrier or instruction semantics changed")
require("return __exynos_smc(cmd, arg1, arg2, arg3)" in sw,
        "donor Samsung C wrapper ABI changed")
require("arm_smccc_smc" in native and "struct arm_smccc_res" in native,
        "Linux 5.10 ARM SMCCC API missing")
require("arm_smccc_smc(command, arg1, arg2, arg3, 0, 0, 0, 0, &result)" in p22,
        "P22 Linux 5.10 SMC x0..x3 mapping missing")
require("dsb(sy)" in p22, "ARM64 Samsung pre-SMC memory barrier missing")
require("result.a0" in p22 and "last_firmware_status" in p22,
        "must propagate real 32-bit firmware return status")
require("SMC_CMD_FMP_SECURITY" in ufs and "SMC_CMD_SMU" in ufs,
        "donor UFS original secure init sequence missing")
require("CONFIG_FMP_UFS" in ufs and "FMP_DESCTYPE_3" in ufs,
        "donor encrypted PRDT mode selection missing")
require("SMC_CMD_FMP_DISKENC" in fmp and "FMP_DISKKEY_SET" in fmp,
        "original disk crypto key path missing (DO NOT BYPASS)")
require("make encryption disabled by default" in exynos7 and
        "NSSMU" in exynos7,
        "Linux 5.10 Exynos7 default secure mode differs from donor; re-audit")
require("secure_firmware_abi_verified" in p22h and
        "original_prdt_layout_verified" in p22h and
        "original_disk_key_path_verified" in p22h and
        "allow_smc_io" in p22h and
        "secure_storage_ready" in p22h,
        "P22 explicit block-by-default security gates missing")
require("if (!alice_8895_verified(ctx))" in p22,
        "no security gate before real ARM SMC")
require("SMC_CMD_LOG" in ufs,
        "missing original reset secure logging callback")
report = {
    "gate": "P22_STATIC_SMC_ABI_VERIFICATION",
    "kernel": "5.10.262",
    "donor_sha": PIN,
    "donor_4_4_arm64_smc": "dsb sy; smc #0; x0..x3",
    "native_5_10": "arm_smccc_smc() with struct arm_smccc_res.a0",
    "command_ids": {k:hex(v) for k,v in COMMANDS.items()},
    "donor_security_sequence": ["FMP_SECURITY (descriptor 0 or 3)", "SMU_INIT"],
    "donor_disk_key_flow": "SMC_CMD_FMP_DISKENC retained as unsatisfied prerequisite",
    "mainline_exynos7_smu": "encryption disabled by default, NOT EQUIVALENT",
    "compiled_bridge_has_live_hw_client": False,
    "ready_to_flash": False,
}
(output / "p22-smc-abi-audit.json").write_text(json.dumps(report,indent=2)+"\n")
print("P22 PASS: pinned Samsung 4.4 FMP/SMU secure SMC ABI matches actual Linux 5.10 call envelope.")
print("P22 hard gate: original encrypted PRDT/disk-key/firmware behavior remains UNVERIFIED.")
print("P22 no Secure Monitor calls, no UFS hardware probe and NEVER FLASH.")
