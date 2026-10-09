#!/usr/bin/env bash
# P1C2: backport proper PLL1051x/PLL1052x operations from pll0822x family.
set -euo pipefail
TREE="${1:?Usage: $0 /path/to/linux-5.10.262}"
[[ "$(make -s -C "$TREE" kernelversion)" == 5.10.* ]] || {
    echo 'Expected genuine Linux 5.10' >&2; exit 2;
}
export K510_PLL_TREE="$TREE"
python3 - <<'PY'
import os
from pathlib import Path
import urllib.request

root = Path(os.environ["K510_PLL_TREE"]) / "drivers/clk/samsung"
source_url = "https://raw.githubusercontent.com/torvalds/linux/v6.13/drivers/clk/samsung/clk-pll.c"
with urllib.request.urlopen(source_url, timeout=60) as response:
    upstream = response.read().decode("utf-8")

header = root / "clk-pll.h"
hdr = header.read_text()
anchor = "\tpll_1460x,\n"
assert hdr.count(anchor) == 1
if "\tpll_1051x," not in hdr:
    hdr = hdr.replace(anchor, anchor + "\tpll_1051x,\n\tpll_1052x,\n")
    header.write_text(hdr)

cfile = root / "clk-pll.c"
text = cfile.read_text()
if "samsung_pll0822x_recalc_rate" not in text:
    start = upstream.index("/*\n * PLL0822x Clock Type\n */")
    end = upstream.index("/*\n * PLL0831x Clock Type\n */", start)
    block = upstream[start:end]
    # Both Exynos8895 PLL types use the 10-bit MDIV formula.
    block = block.replace(
        "\tif (pll->type != pll_1418x)\n"
        "\t\tmdiv = (pll_con3 >> PLL0822X_MDIV_SHIFT) & PLL0822X_MDIV_MASK;\n"
        "\telse\n"
        "\t\tmdiv = (pll_con3 >> PLL0822X_MDIV_SHIFT) & PLL1418X_MDIV_MASK;",
        "\tmdiv = (pll_con3 >> PLL0822X_MDIV_SHIFT) & PLL0822X_MDIV_MASK;")
    block = block.replace("\tif (pll->type == pll_0516x)\n\t\tfvco *= 2;\n", "")
    block = block.replace("\tu32 mdiv_mask, pll_con3;", "\tu32 pll_con3;")
    block = block.replace(
        "\tif (pll->type != pll_1418x)\n"
        "\t\tmdiv_mask = PLL0822X_MDIV_MASK;\n"
        "\telse\n"
        "\t\tmdiv_mask = PLL1418X_MDIV_MASK;\n", "")
    block = block.replace("mdiv_mask << PLL0822X_MDIV_SHIFT",
                          "PLL0822X_MDIV_MASK << PLL0822X_MDIV_SHIFT")
    # Linux 5.10's samsung_pll3xxx_enable may spin forever on failed lock.
    lock_helper = (
        "static int k510_pll0822x_wait_lock(struct samsung_clk_pll *pll)\n"
        "{\n"
        "\tunsigned int i;\n"
        "\tfor (i = 0; i < 100000; ++i) {\n"
        "\t\tif (readl_relaxed(pll->con_reg) & BIT(pll->lock_offs))\n"
        "\t\t\treturn 0;\n"
        "\t\tcpu_relax();\n"
        "\t}\n"
        "\tpr_err(\"k510: PLL did not lock: %s\\n\", clk_hw_get_name(&pll->hw));\n"
        "\treturn -ETIMEDOUT;\n"
        "}\n\n"
        "static int k510_pll0822x_enable(struct clk_hw *hw)\n"
        "{\n"
        "\tstruct samsung_clk_pll *pll = to_clk_pll(hw);\n"
        "\tu32 val = readl_relaxed(pll->con_reg);\n"
        "\twritel_relaxed(val | BIT(pll->enable_offs), pll->con_reg);\n"
        "\treturn k510_pll0822x_wait_lock(pll);\n"
        "}\n\n")
    block = block.replace(
        "static unsigned long samsung_pll0822x_recalc_rate",
        lock_helper + "static unsigned long samsung_pll0822x_recalc_rate")
    block = block.replace("samsung_pll_lock_wait(pll, BIT(pll->lock_offs))",
                          "k510_pll0822x_wait_lock(pll)")
    block = block.replace(".enable = samsung_pll3xxx_enable,",
                          ".enable = k510_pll0822x_enable,")
    assert "pll_1418x" not in block and "pll_0516x" not in block
    assert "mdiv_mask" not in block
    assert "samsung_pll_lock_wait" not in block
    assert block.count("k510_pll0822x_wait_lock(pll)") == 2
    anchor = "/*\n * PLL36xx Clock Type\n */"
    assert text.count(anchor) == 1
    text = text.replace(anchor, block + anchor)

if "case pll_1051x:" not in text:
    insert_at = "\tcase pll_4500:"
    assert text.count(insert_at) == 1
    replacement = (
        "\tcase pll_1051x:\n"
        "\tcase pll_1052x:\n"
        "\t\tpll->enable_offs = PLL0822X_ENABLE_SHIFT;\n"
        "\t\tpll->lock_offs = PLL0822X_LOCK_STAT_SHIFT;\n"
        "\t\tif (!pll->rate_table)\n"
        "\t\t\tinit.ops = &samsung_pll0822x_clk_min_ops;\n"
        "\t\telse\n"
        "\t\t\tinit.ops = &samsung_pll0822x_clk_ops;\n"
        "\t\tbreak;\n"
    )
    text = text.replace(insert_at, replacement + insert_at)
cfile.write_text(text)

donor = root / "clk-exynos8895.c"
if donor.exists():
    data = donor.read_text()
    data = data.replace("of_device_get_match_data(dev)", "device_get_match_data(dev)")
    donor.write_text(data)
assert "case pll_1051x:" in cfile.read_text()
assert "case pll_1052x:" in cfile.read_text()
print("P1C2: PLL1051x/1052x recalc+rate+bounded-lock backport staged")
print("Hardware clock behavior is NOT yet validated.")
PY
