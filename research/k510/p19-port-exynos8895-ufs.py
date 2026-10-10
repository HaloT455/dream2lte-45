#!/usr/bin/env python3
"""P19: port Exynos8895 4.4 UniPro vendor calibration + host variant to
the REAL Linux 5.10 ufs-exynos.c variant API. Fail closed, NO BOOT.
This is NOT a standalone raw 4.4 compilation hack, nor a hardware test.
"""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
if len(sys.argv) != 4:
    raise SystemExit("Usage: p19-port-exynos8895-ufs.py DONOR_GIT LINUX_5_10_TREE EVIDENCE_DIR")
donor, kernel, evidence = map(Path, sys.argv[1:])
evidence.mkdir(parents=True, exist_ok=True)
PIN = "3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3"
def donor_file(path):
    return subprocess.check_output(
        ["git","-C",str(donor),"show",f"{PIN}:{path}"]
    ).decode()
def require(ok, why):
    if not ok:
        raise SystemExit("P19 REFUSED: "+why)

original_dts = donor_file("arch/arm64/boot/dts/exynos/exynos8895.dtsi")
original_source = donor_file("drivers/scsi/ufs/ufs-exynos.c")
native = kernel / "drivers/scsi/ufs/ufs-exynos.c"
dtb_text = (kernel / "arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts").read_text()
require('status = "disabled"' in dtb_text, "DTS UFS safety status missing")
require(original_source.count("struct ufs_hba_variant_ops exynos_ufs_ops") == 1,
        "original vendor driver not recognized")
# Extract ONLY the dedicated UFS node, bounded by the next sibling.
m = re.search(r"\bufs@0x11120000\s*\{",original_dts)
require(bool(m), "donor UFS node not found")
start = m.end()
level = 1
end = 0
for i in range(start, len(original_dts)):
    if original_dts[i] == '{': level += 1
    if original_dts[i] == '}':
        level -= 1
        if not level: end=i; break
require(end>start, "donor UFS node truncated")
dts=original_dts[start:end]
# Strip both kinds of comments to guard against data parsed from comments.
dts=re.sub(r"/\*.*?\*/","",dts,flags=re.S)
dts=re.sub(r"//[^\n]*","",dts)
table_keys=[
    ("phy-init","pre_link"),
    ("post-phy-init","post_link"),
    ("calib-of-pwm","pwm"),
    ("calib-of-hs-rate-a","hs_a"),
    ("calib-of-hs-rate-b","hs_b"),
]
entries={}
for dt_key,alias in table_keys:
    mm=re.search(r"(?m)^\s*"+re.escape(dt_key)+r"\s*=\s*(.*?);",dts,re.S)
    require(bool(mm),"missing original vendor property "+dt_key)
    vals=re.findall(r"<([^>]+)>",mm.group(1))
    target=[]
    for v in vals:
        bits=v.split()
        if len(bits) != 4:
            raise SystemExit(f"P19 REFUSED unexpected {dt_key} config tuple {bits}")
        if bits == ['0','0','0','0']:
            continue
        # Port only vendor UIC *standard MIB* commands supported by 5.10.
        # Proprietary PCS/PMA/PHY timing writes MUST BE A SEPARATE PHY PORT.
        if bits[3] != "UNIPRO_STD_MIB":
            continue
        require(bits[2] in {"PMD_ALL","PMD_HS","PMD_PWM"},
                f"unsupported power-mode mask in {dt_key}: {bits[2]}")
        try: addr=int(bits[0],0); value=int(bits[1],0)
        except ValueError as err:
            raise SystemExit(f"P19 REFUSED nonnumeric UIC value: {bits}") from err
        require(0 <= addr <= 0xffff and 0 <= value <= 0xffffffff,
                f"invalid UIC MIB entry: {bits}")
        target.append((addr,value))
    require(len(target)>0,"no standard UniPro MIB entries in "+dt_key)
    entries[alias]=target
require(len(entries["pre_link"])>=4,"missing Exynos8895 identity UIC attributes")
require(any(addr==0x15a4 for addr,value in entries["post_link"]),
        "missing Exynos8895 post-link PA SaveConfigTime")
preamble="""/* ALICE_K510_P19_EXYNOS8895_VENDOR_UNIPRO_PORT
 * Source: genuine Samsung V12R5T Exynos8895 DTS pinned at
 * 3ea6f1b4341c0bd9e0e020567fa334da4a1a24c3
 * This is a strict *subset* of the original UFS driver:
 *   - standard UniPro MIB programming through Linux 5.10 ufshcd_dme_set;
 *   - phy PCS/PMA and proprietary FMP/SMC/MMIO are not translated.
 * Never enable the Exynos8895 UFS node until PHY/power/security is ported.
 */
struct alice8895_uic_step {
    u16 mib;
    u32 value;
};
"""
body=[preamble]
for mode,arr in entries.items():
    body.append(f"static const struct alice8895_uic_step alice8895_{mode}[] = {{\n")
    body += [f"\t{{ 0x{addr:04x}, 0x{val:x} }},\n" for addr,val in arr]
    body.append("};\n")
body.append("""
static int alice8895_apply_uic_table(struct exynos_ufs *ufs,
                                      const struct alice8895_uic_step *steps,
                                      size_t count)
{
    size_t i;
    int ret;

    for (i = 0; i < count; i++) {
        ret = ufshcd_dme_set(ufs->hba, UIC_ARG_MIB(steps[i].mib),
                             steps[i].value);
        if (ret) {
            dev_err(ufs->hba->dev,
                    "Exynos8895 vendor UniPro MIB 0x%x failed: %d\\n",
                    steps[i].mib, ret);
            return ret;
        }
    }
    return 0;
}

static int exynos8895_ufs_pre_link(struct exynos_ufs *ufs)
{
    int ret;

    ret = alice8895_apply_uic_table(ufs, alice8895_pre_link,
                                   ARRAY_SIZE(alice8895_pre_link));
    if (ret)
        return ret;
    /* Existing v5.10 Exynos host link and clock handling preserved. */
    return exynos7_ufs_pre_link(ufs);
}

static int exynos8895_ufs_post_link(struct exynos_ufs *ufs)
{
    int ret = exynos7_ufs_post_link(ufs);
    if (ret)
        return ret;

    return alice8895_apply_uic_table(ufs, alice8895_post_link,
                                     ARRAY_SIZE(alice8895_post_link));
}

static int exynos8895_ufs_pre_pwr_change(struct exynos_ufs *ufs,
                                        struct ufs_pa_layer_attr *pwr)
{
    const struct alice8895_uic_step *tbl;
    size_t count;
    int ret;

    if (ufshcd_is_hs_mode(pwr)) {
        if (pwr->hs_rate == PA_HS_MODE_B) {
            tbl=alice8895_hs_b;
            count=ARRAY_SIZE(alice8895_hs_b);
        } else {
            tbl=alice8895_hs_a;
            count=ARRAY_SIZE(alice8895_hs_a);
        }
    } else {
        tbl=alice8895_pwm;
        count=ARRAY_SIZE(alice8895_pwm);
    }
    ret=alice8895_apply_uic_table(ufs,tbl,count);
    if (ret)
        return ret;
    return exynos7_ufs_pre_pwr_change(ufs,pwr);
}
""")
native_original=native.read_text()
require("ALICE_K510_P19" not in native_original,"already ported in this tree")
anchor="/*\n * exynos_ufs_auto_ctrl_hcc - HCI core clock control by h/w"
require(native_original.count(anchor)==1,"upstream 5.10 driver insertion anchor changed")
patched=native_original.replace(anchor,"".join(body)+"\n"+anchor,1)
decl="struct exynos_ufs_drv_data exynos_ufs_drvs = {"
require(patched.count(decl)==1,"native drv-data anchor changed")
# Exynos8895 variant intentionally uses only generic 5.10 host quirk baseline;
# vendor-only hardware quirks need separate proof, so do NOT fake equivalence.
variant="""struct exynos_ufs_drv_data exynos8895_ufs_drvs = {
    .compatible       = "samsung,exynos8895-ufs",
    .uic_attr         = &exynos7_uic_attr,
    .quirks           = UFSHCI_QUIRK_BROKEN_REQ_LIST_CLR,
    .opts             = EXYNOS_UFS_OPT_HAS_APB_CLK_CTRL,
    .drv_init         = exynos7_ufs_drv_init,
    .pre_link         = exynos8895_ufs_pre_link,
    .post_link        = exynos8895_ufs_post_link,
    .pre_pwr_change   = exynos8895_ufs_pre_pwr_change,
    .post_pwr_change  = exynos7_ufs_post_pwr_change,
};

"""
patched=patched.replace(decl,variant+decl,1)
old_parser="struct exynos_ufs_drv_data *drv_data = &exynos_ufs_drvs;"
require(patched.count(old_parser)==1,"native DT matching implementation changed")
patched=patched.replace(
    old_parser,
    """struct exynos_ufs_drv_data *drv_data = &exynos_ufs_drvs;

    if (of_device_is_compatible(np, "samsung,exynos8895-ufs"))
        drv_data = &exynos8895_ufs_drvs;""",
    1,
)
needle='''\t{ .compatible = "samsung,exynos7-ufs",
\t  .data\t      = &exynos_ufs_drvs },'''
require(patched.count(needle)==1,"native OF compatibility table changed")
patched=patched.replace(
    needle,
    needle+'''
    { .compatible = "samsung,exynos8895-ufs",
      .data = &exynos8895_ufs_drvs },''',1
)
native.write_text(patched)
# Bind the strict Exynos8895-compatible to a disabled-only board node,
# so DTB can prove matching without calling probe on physical hardware.
dts_path=kernel/"arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
dts_current=dts_path.read_text()
node_start=dts_current.find("alice_ufs_embd: ufs@11120000")
require(node_start>=0,"5.10 research UFS node not found")
node_close=dts_current.find("};",node_start)
require(node_close>node_start,"UFS research node terminator not found")
node=dts_current[node_start:node_close]
require('compatible = "samsung,exynos7-ufs";' in node,"native UFS compatible unexpected")
require('status = "disabled";' in node,"refuse UFS hardware probe")
dts_current = dts_current[:node_start] + node.replace(
    'compatible = "samsung,exynos7-ufs";',
    'compatible = "samsung,exynos8895-ufs";',
) + dts_current[node_close:]
dts_path.write_text(dts_current)
# Do not accidentally enable a PMIC or any physical storage writes.
assert 'status = "disabled";' in dts_path.read_text()
manifest={
    "stage":"P19_PORTED_EXYNOS8895_STANDARD_UNIPRO_HOST_VARIANT_C_ONLY",
    "donor_revision":PIN,
    "upstream_version":"5.10.262",
    "donor_original_vendor_c_sha256":hashlib.sha256(original_source.encode()).hexdigest(),
    "vendor_UIC_MIB_tables":{key:{
        "ported_entries":len(vals),
        "entries":[{"mib":hex(a),"value":hex(v)} for a,v in vals]
    } for key,vals in entries.items()},
    "port_includes":"Linux 5.10 native host callback/API + original vendor standard UniPro MIB subset",
    "PHY_PCS_PMA_calibration_ported":False,
    "SMC_FMP_security_ported":False,
    "Samsung_Speedy_and_ACPM_runtime_ported":False,
    "UFS_device_tree_status":"disabled",
    "runtime_hardware_tested":False,
    "ready_to_flash":False,
}
(evidence/"p19-ported-vendor-unipro.json").write_text(json.dumps(manifest,indent=2)+"\n")
(evidence/"ported-ufs-exynos.c.sha256").write_text(
    hashlib.sha256(patched.encode()).hexdigest()+"  drivers/scsi/ufs/ufs-exynos.c\n"
)
print("P19: 4.4 Exynos8895 UniPro standard MIB tables ported to 5.10 modern host callbacks.")
print("P19: "+str({k:len(v) for k,v in entries.items()}))
print("P19 guard: vendor PHY/SMC/PMIC not operational; UFS DT disabled; NEVER FLASH.")
