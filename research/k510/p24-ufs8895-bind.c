// SPDX-License-Identifier: GPL-2.0
/*
 * P24 EXYNOS8895 UFS lab-only platform binding for native Linux 5.10.
 *
 * IMPORTANT: This is a live Linux platform_driver but matches ONLY the
 * P24 experimental compatible. Its DT node remains status="disabled".
 * It cannot call ufshcd_pltfrm_init unless an independent firmware/board
 * audit has explicitly set alice,hardware-audit-passed; absent by default.
 * Even that deliberately does not set P23 firmware/PMIC/SMC readiness.
 * NO P24 CI or default kernel can access UFS/secure monitor hardware.
 */
#include <linux/clk.h>
#include <linux/errno.h>
#include <linux/err.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/regulator/consumer.h>
#include <linux/slab.h>
#include "ufshcd.h"
#include "ufshcd-pltfrm.h"
#include "alice-ufs8895-host.h"

#define ALICE_8895_LAB_COMPAT "alice,exynos8895-ufs-research"

static int alice_8895_map_region(struct platform_device *pdev,
				 const char *name,
				 void __iomem **mapped, u32 *size)
{
	struct resource *res;
	void __iomem *base;

	res = platform_get_resource_byname(pdev, IORESOURCE_MEM, name);
	if (!res || resource_size(res) < sizeof(u32) ||
	    resource_size(res) > U32_MAX)
		return -EINVAL;
	base = devm_platform_ioremap_resource_byname(pdev, name);
	if (IS_ERR(base))
		return PTR_ERR(base);
	*mapped = base;
	if (size)
		*size = (u32)resource_size(res);
	return 0;
}

/* Does nothing irreversible; calls no SMC, MMIO read/write or regulator on.
 * The P23 code alone controls power, and ALL its authorization flags
 * remain false following context allocation.
 */
int alice_8895_ufs_bind_host(struct ufs_hba *hba)
{
	struct platform_device *pdev;
	struct alice_8895_host *ctx;
	struct device *dev;
	int ret;

	if (!hba || !hba->dev || !hba->dev->of_node)
		return -EINVAL;
	dev = hba->dev;
	if (!of_device_is_compatible(dev->of_node, ALICE_8895_LAB_COMPAT))
		return -ENODEV;
	pdev = to_platform_device(dev);
	if (ufshcd_get_variant(hba))
		return -EBUSY;
	ctx = devm_kzalloc(dev, sizeof(*ctx), GFP_KERNEL);
	if (!ctx)
		return -ENOMEM;

	/* hba mmio index 0 is mapped by ufshcd_pltfrm_init. */
	ctx->io.hba = hba;
	ret = alice_8895_map_region(pdev, "vs_hci", &ctx->io.hci,
				    &ctx->io.hci_bytes);
	if (ret)
		return ret;
	ret = alice_8895_map_region(pdev, "unipro", &ctx->io.unipro,
				    &ctx->io.unipro_bytes);
	if (ret)
		return ret;
	ret = alice_8895_map_region(pdev, "phy_pma", &ctx->io.pma,
				    &ctx->io.pma_bytes);
	if (ret)
		return ret;
	ret = alice_8895_map_region(pdev, "phy_isolation",
				    &ctx->phy_isolation, NULL);
	if (ret)
		return ret;
	ret = alice_8895_map_region(pdev, "io_coherency",
				    &ctx->sys_coherency, NULL);
	if (ret)
		return ret;
	ret = alice_8895_map_region(pdev, "tcxo_select",
				    &ctx->sys_tcxo, NULL);
	if (ret)
		return ret;

	/* Pinned 4.4 8895: 2 lanes, gate clock GATE_UFS_EMBD and
	 * UniPro clock UFS_EMBD. Real clock phandles are NOT in P24 DT.
	 */
	ctx->hci_clk = devm_clk_get(dev, "GATE_UFS_EMBD");
	if (IS_ERR(ctx->hci_clk))
		return PTR_ERR(ctx->hci_clk);
	ctx->unipro_clk = devm_clk_get(dev, "UFS_EMBD");
	if (IS_ERR(ctx->unipro_clk))
		return PTR_ERR(ctx->unipro_clk);
	ctx->vcc = devm_regulator_get(dev, "vcc");
	if (IS_ERR(ctx->vcc))
		return PTR_ERR(ctx->vcc);

	ctx->io.lanes = 2;
	ctx->io.mclk_hz = clk_get_rate(ctx->unipro_clk);
	ctx->io.pclk_hz = clk_get_rate(ctx->unipro_clk);
	if (!ctx->io.mclk_hz || !ctx->io.pclk_hz)
		return -EINVAL;

	/* Bind only identity + resource handles. Deliberately DO NOT set
	 * allow_hardware, board_resources_verified, acpm_firmware_verified,
	 * speedy_pmic_verified, secure_firmware_verified, etc.
	 */
	ctx->signature = ALICE_8895_HOST_SIGNATURE;
	ufshcd_set_variant(hba, ctx);
	return 0;
}

/* A research-compatible node is mandatory; an accidental DT "okay"
 * without audit property fails BEFORE ufshcd_pltfrm_init, which would
 * otherwise touch host registers during initialization.
 */
static int alice_8895_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;

	if (!of_device_is_compatible(dev->of_node, ALICE_8895_LAB_COMPAT))
		return -ENODEV;
	if (!of_property_read_bool(dev->of_node,
				   "alice,hardware-audit-passed")) {
		dev_warn(dev, "Exynos8895 UFS hardware gate CLOSED, no probe\n");
		return -EPERM;
	}
	/* Gate #2: all P23 verification fields are still false. The P23
	 * variant init will return -EPERM before power/MMIO/SMC operations.
	 * This call is here to prove the actual 5.10 entrypoint links.
	 */
	return ufshcd_pltfrm_init(pdev, alice_8895_get_host_ops());
}

static const struct of_device_id alice_8895_match[] = {
	{ .compatible = ALICE_8895_LAB_COMPAT },
	{ }
};
MODULE_DEVICE_TABLE(of, alice_8895_match);

static struct platform_driver alice_8895_driver = {
	.probe = alice_8895_probe,
	.driver = {
		.name = "alice8895-ufs-research-noflash",
		.of_match_table = alice_8895_match,
	},
};
/* Built-in Linux 5.10 platform matching; DT status disabled by P24.
 * Never package this testing kernel as a production or phone-flash boot.
 */
builtin_platform_driver(alice_8895_driver);
