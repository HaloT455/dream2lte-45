#!/usr/bin/env bash
# P1C compile-port experiment: Exynos8895 v6.13 clock data + 5.10 helper adapter.
# This adapter is preliminary; no hardware boot validation, no flash.
set -euo pipefail
TREE="${1:?Usage: $0 /path/to/linux-5.10.262}"
[[ "$(make -s -C "$TREE" kernelversion)" == 5.10.* ]] || exit 3
DIR="$TREE/drivers/clk/samsung"
curl --fail --location --silent --show-error --retry 3 \
  https://raw.githubusercontent.com/torvalds/linux/v6.13/drivers/clk/samsung/clk-exynos8895.c \
  -o "$DIR/clk-exynos8895.c"
test -s "$DIR/clk-exynos8895.c"
cat > "$DIR/clk-exynos-arm64.h" <<'HDR'
/* SPDX-License-Identifier: GPL-2.0-only */
/* Alice P1C Linux 5.10 compatibility shim; Exynos8895 only. */
#ifndef __K510_EXYNOS_ARM64_H
#define __K510_EXYNOS_ARM64_H
#include "clk.h"
void exynos_arm64_register_cmu(struct device *dev, struct device_node *np,
                              const struct samsung_cmu_info *cmu);
#endif
HDR
cat > "$DIR/clk-exynos8895-adapter.c" <<'C'
// SPDX-License-Identifier: GPL-2.0-only
/* Alice K510 P1C preliminary compatibility adapter for Linux 5.10 clocks.
 * NOT hardware validated. Must be audited for PM and CLK gate access before boot.
 */
#include <linux/clk.h>
#include <linux/io.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/of_clk.h>
#include <linux/platform_device.h>
#include "clk.h"
#include "clk-exynos-arm64.h"

#define GATE_MANUAL BIT(20)
#define GATE_ENABLE_HWACG BIT(28)
static bool is_gate_reg(unsigned long off)
{
    return off >= 0x2000 && off <= 0x2fff;
}

void __init exynos_arm64_register_cmu(struct device *dev,
                       struct device_node *np,
                       const struct samsung_cmu_info *cmu)
{
    struct clk *parent_clk = NULL;
    void __iomem *base;
    size_t i;

    if (cmu->clk_name) {
        parent_clk = dev ? clk_get(dev, cmu->clk_name) :
                           of_clk_get_by_name(np, cmu->clk_name);
        if (IS_ERR(parent_clk)) {
            pr_warn("k510: Exynos8895 parent clock %s unavailable (%ld)\n",
                    cmu->clk_name, PTR_ERR(parent_clk));
            parent_clk = NULL;
        } else if (clk_prepare_enable(parent_clk)) {
            pr_warn("k510: Exynos8895 parent clock %s enable failed\n",
                    cmu->clk_name);
        }
    }

    base = of_iomap(np, 0);
    if (!base)
        panic("k510: cannot map Exynos8895 CMU registers\n");

    /* Preserve upstream 6.13 default gate manual mode for CMU gate registers.
     * Clock PLL manual control is off by default for Exynos8895 donor.
     */
    for (i = 0; i < cmu->nr_clk_regs; i++) {
        unsigned long off = cmu->clk_regs[i];
        if (is_gate_reg(off)) {
            u32 value = readl(base + off);
            writel((value | GATE_MANUAL) & ~GATE_ENABLE_HWACG, base + off);
        }
    }
    iounmap(base);
    samsung_cmu_register_one(np, cmu);
}
C
python3 - "$DIR/Makefile" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]); text=p.read_text()
entry='\n# Alice K510 P1C Exynos8895 clock data + temporary 5.10 adapter\nobj-$(CONFIG_EXYNOS_ARM64_COMMON_CLK) += clk-exynos8895.o clk-exynos8895-adapter.o\n'
if 'clk-exynos8895-adapter.o' not in text:
    p.write_text(text.rstrip()+'\n'+entry)
PY
echo "P1C source imported. Compilation needed; clock PM behavior still NOT boot-validated."
