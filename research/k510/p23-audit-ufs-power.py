#!/usr/bin/env python3
"""P23 pinned Exynos8895 UFS source power/clock/host ABI audit.

This script does not probe hardware. It ensures P23 does not silently equate
a GPIO fixed UFS VCC to S2MPS17 outputs nor reuse Exynos7 host bindings.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

PIN = "3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3"

def read_pin(repo, path):
    return subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{PIN}:{path}"], text=True)

def need(cond, message):
    if not cond:
        raise SystemExit("P23 ABI AUDIT FAILED: " + message)

if len(sys.argv) != 4:
    raise SystemExit("usage: p23-audit-ufs-power.py DONOR LINUX510 OUT_JSON")
donor, kernel, out = map(Path, sys.argv[1:])
dts = read_pin(donor, "arch/arm64/boot/dts/exynos/exynos8895.dtsi")
ufs = read_pin(donor, "drivers/scsi/ufs/ufs-exynos.c")
smch = read_pin(donor, "include/linux/smc.h")
v510 = (kernel / "drivers/scsi/ufs/ufshcd.h").read_text()
v510_driver = (kernel / "drivers/scsi/ufs/ufs-exynos.c").read_text()
h = (kernel / "drivers/scsi/ufs/alice-ufs8895-host.h").read_text()
c = (kernel / "drivers/scsi/ufs/alice-ufs8895-host.c").read_text()

# UFS has several nested child nodes. A first-closing-brace regex would
# truncate the PHY subtree and miss sysreg mappings. Use the pinned sibling
# label as the explicit end of this donor's UFS region (same P20 boundary).
begin = dts.find("ufs@0x11120000 {")
end = dts.find("ufs_fixed_vcc:", begin)
need(begin >= 0 and end > begin, "pinned donor UFS/fixed-VCC node bounds")
n = dts[begin:end]
fixed = re.search(r'ufs_fixed_vcc:\s*fixedregulator@0\s*\{(.*?)\n\s*\};', dts, re.S)
need(fixed is not None, "pinned donor fixed regulator missing")
f = fixed.group(1)
need('compatible ="samsung,exynos-ufs"' in n, "original vendor UFS compatible")
need('vcc-supply = <&ufs_fixed_vcc>' in n, "GPIO UFS VCC supply")
need('compatible = "regulator-fixed"' in f, "VCC is not fixed regulator")
need('gpio = <&gpg0 0 0>' in f, "fixed VCC GPIO changed")
need('regulator-boot-on' in f, "fixed VCC boot state changed")
need('"GATE_UFS_EMBD"' in n and '"UFS_EMBD"' in n, "UFS clock names")
for physical in ("0x11120000", "0x11121100", "0x11110000",
                 "0x11130000", "0x11124000", "0x16480724",
                 "0x11020700", "0x11021150"):
    need(physical in n, "missing original register " + physical)
need("exynos_ufs_init_system" in ufs and "exynos_ufs_ctrl_phy_pwr" in ufs,
     "original system init missing")
need("HCI_SW_RST" in ufs and "HCI_GPIO_OUT" in ufs,
     "original HCI reset missing")
need("exynos_ufs_config_smu" in ufs and "exynos_ufs_setup_clocks" in ufs,
     "original FMP/clock sequencing missing")
need("SMC_CMD_FMP_SECURITY" in smch, "original SMC ABI missing")
need("struct ufs_hba_variant_ops {" in v510,
     "Linux 5.10 host callback declaration missing")
for field in ("setup_clocks", "setup_regulators", "hce_enable_notify",
              "link_startup_notify", "pwr_change_notify", "suspend",
              "resume"):
    need(re.search(r'\(\s*\*' + field + r'\)', v510),
         "native variant callback ABI missing: " + field)
need("struct ufs_hba_variant_ops" in v510_driver,
     "native Linux 5.10 host driver absent")
need("alice_8895_host_validate" in h and
     "alice_8895_get_host_ops" in h, "P23 host ABI header missing")
need("regulator_enable(ctx->vcc)" in c, "fixed VCC sequence missing")
need("alice_8895_ufs_secure_init" in c,
     "P22 SMC power dependency missing")
need("alice_ufs8895_run_phase" in c, "P21 PHY callback integration missing")
need("return -EOPNOTSUPP;" in c, "unsafe unsupported power states")
need("status = \"disabled\"" in
     (kernel / "arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts").read_text(),
     "UFS must stay disabled")
for token in ("ufshcd_pltfrm_init(", "module_platform_driver(",
              "builtin_platform_driver(", ".of_match_table ="):
    need(token not in c, "P23 must not register hardware: " + token)

report = {
    "donor_pin": PIN,
    "kernel": "Linux 5.10.262",
    "ufs_vcc_type": "GPIO-controlled regulator-fixed",
    "ufs_vcc_gpio": "gpg0[0]",
    "ufs_vcc_regulator_boot_on": True,
    "ufs_vcc_direct_s2mps17_rail": False,
    "clock_names": ["GATE_UFS_EMBD", "UFS_EMBD"],
    "vendor_host_hci": "0x11121100",
    "phy_pma_base": "0x11124000",
    "phy_isolation_register": "0x16480724",
    "coherency_register": "0x11020700",
    "tcxo_register": "0x11021150",
    "native_callback_abi_audited": True,
    "smccc_power_gate": "fail-closed",
    "registers_platform_driver": False,
    "ufs_dts_enabled": False,
    "runtime_verified": False,
    "flashable": False,
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2) + "\n")
print("P23 PINNED DONOR POWER/ABI AUDIT PASS; GPIO VCC != direct S2MPS17")
