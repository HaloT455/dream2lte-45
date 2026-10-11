// SPDX-License-Identifier: GPL-2.0
/*
 * P23 Exynos8895 UFS host integration LAB for genuine Linux 5.10.262.
 *
 * Zero registered clients/platform drivers, no DT match. Real callbacks
 * and power dependencies are implemented, but cannot be invoked by
 * Linux UFS core until a separate, reviewed P24+ platform binding exists.
 *
 * 4.4 source: Exynos8895 ufs-exynos.c init_system/init_host/host_reset,
 * setup_clocks, link_startup_notify, pwr_change_notify, suspend/resume.
 */
#include <linux/bitops.h>
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/iopoll.h>
#include <linux/kernel.h>
#include <linux/regmap.h>
#include <linux/regulator/consumer.h>
#include "ufshcd.h"
#include "unipro.h"
#include "alice-ufs8895-calibration.h"
#include "alice-ufs8895-engine.h"
#include "alice-ufs8895-smc.h"
#include "alice-ufs8895-host.h"

#define ALICE_8895_HCI_SW_RST	0x50U
#define ALICE_8895_HCI_GPIO_OUT	0x70U
#define ALICE_8895_HCI_RESET_MASK	(BIT(0) | BIT(1))
#define ALICE_8895_IO_COHERENCY_MASK	(BIT(8) | BIT(9))
#define ALICE_8895_TCXO_SEL_MASK	BIT(0)

/* UFS fixed GPIO VCC from pinned 8895 DTS; NOT a direct S2MPS17 rail. */
int alice_8895_host_validate(const struct alice_8895_host *ctx)
{
	int ret;

	if (!ctx || ctx->signature != ALICE_8895_HOST_SIGNATURE ||
	    !ctx->allow_hardware || !ctx->board_resources_verified ||
	    !ctx->acpm_firmware_verified || !ctx->speedy_pmic_verified ||
	    !ctx->vcc_gpio_mapping_verified ||
	    !ctx->clock_ownership_verified ||
	    !ctx->pmu_isolation_verified ||
	    !ctx->sysreg_ownership_verified || !ctx->secure_firmware_verified)
		return -EPERM;

	if (IS_ERR_OR_NULL(ctx->vcc) ||
	    IS_ERR_OR_NULL(ctx->hci_clk) ||
	    IS_ERR_OR_NULL(ctx->unipro_clk) ||
	    IS_ERR_OR_NULL(ctx->pmu) ||
	    !ctx->phy_isolation || !ctx->sys_coherency ||
	    !ctx->sys_tcxo || !ctx->io.hba || !ctx->io.hci ||
	    !ctx->io.unipro || !ctx->io.pma ||
	    ctx->io.hci_bytes < ALICE_8895_HCI_GPIO_OUT + 4 ||
	    ctx->io.unipro_bytes < 4 || ctx->io.pma_bytes < 4 ||
	    (ctx->io.lanes != 1 && ctx->io.lanes != 2) ||
	    ctx->io.mclk_hz == 0 || ctx->io.pclk_hz == 0)
		return -EINVAL;

	if (ctx->smc.smu_ready || ctx->smc.fmp_ready)
		return -EINVAL; /* no stale secure state when acquiring power */
	if (!ctx->smc.enable_firmware_calls ||
	    !ctx->smc.firmware_abi_verified ||
	    !ctx->smc.ufs_power_verified)
		return -EPERM;

	/* Phase 0 entire table must be preflight-safe before any write. */
	ret = alice_ufs8895_check_phase(&ctx->io, 0, NULL);
	return ret;
}

static struct alice_8895_host *alice_8895_ctx(struct ufs_hba *hba)
{
	struct alice_8895_host *ctx;

	if (!hba)
		return NULL;
	ctx = ufshcd_get_variant(hba);
	if (!ctx || ctx->signature != ALICE_8895_HOST_SIGNATURE ||
	    ctx->io.hba != hba)
		return NULL;
	return ctx;
}

static void alice_8895_release_resources(struct alice_8895_host *ctx)
{
	if (!ctx)
		return;

	/* No power-down until the PHY is isolated and the secure state
	 * cannot be mistaken for a still-initialized storage controller.
	 */
	ctx->link_started = false;
	ctx->secure_ready = false;
	ctx->link_prepared = false;
	ctx->smc.smu_ready = false;
	ctx->smc.fmp_ready = false;
	ctx->io.allow_hardware_io = false;

	if (ctx->phy_isolation && ctx->pmu_isolation_verified &&
	    ctx->hci_clk_owned)
		writel(0, ctx->phy_isolation); /* donor PHY-isolation false */

	if (ctx->unipro_clk_owned) {
		clk_disable_unprepare(ctx->unipro_clk);
		ctx->unipro_clk_owned = false;
	}
	if (ctx->hci_clk_owned) {
		clk_disable_unprepare(ctx->hci_clk);
		ctx->hci_clk_owned = false;
	}
	if (ctx->vcc_owned) {
		regulator_disable(ctx->vcc);
		ctx->vcc_owned = false;
	}
}

static int alice_8895_prepare_power(struct alice_8895_host *ctx)
{
	u32 old_coh, old_tcxo;
	int ret;

	ret = alice_8895_host_validate(ctx);
	if (ret)
		return ret;
	if (ctx->vcc_owned || ctx->hci_clk_owned ||
	    ctx->unipro_clk_owned || ctx->link_prepared)
		return -EBUSY;

	/* Order: VCC GPIO-controlled fixed regulator -> HCI/UniPro clocks ->
	 * sysregs -> PHY isolation -> secure monitor. ACPM and Speedy PMIC
	 * readiness are explicit preconditions, never assumed from Kbuild.
	 */
	ret = regulator_enable(ctx->vcc);
	if (ret)
		return ret;
	ctx->vcc_owned = true;

	ret = clk_prepare_enable(ctx->hci_clk);
	if (ret)
		goto err;
	ctx->hci_clk_owned = true;

	ret = clk_prepare_enable(ctx->unipro_clk);
	if (ret)
		goto err;
	ctx->unipro_clk_owned = true;

	/* Never write entire sysreg blind: preserve unrelated bits. */
	old_coh = readl(ctx->sys_coherency);
	old_tcxo = readl(ctx->sys_tcxo);
	writel(old_coh | ALICE_8895_IO_COHERENCY_MASK,
	       ctx->sys_coherency);
	writel(old_tcxo | ALICE_8895_TCXO_SEL_MASK, ctx->sys_tcxo);

	writel(1, ctx->phy_isolation); /* exactly donor writel(!!en) */
	ret = alice_8895_ufs_secure_init(&ctx->smc, ctx->fmp_ufs_enabled);
	if (ret) {
		writel(old_coh, ctx->sys_coherency);
		writel(old_tcxo, ctx->sys_tcxo);
		goto err;
	}
	ctx->secure_ready = true;
	ctx->link_prepared = true;

	/* P21 checks all UFS registers and is never given I/O permission
	 * until the power/clock/secure sequence is complete.
	 */
	ctx->io.allow_hardware_io = true;
	return 0;

err:
	alice_8895_release_resources(ctx);
	return ret;
}

static int alice_8895_host_reset(struct alice_8895_host *ctx)
{
	u32 value;
	int ret;

	if (!ctx->link_prepared || !ctx->secure_ready ||
	    !ctx->io.allow_hardware_io)
		return -EPERM;
	writel(ALICE_8895_HCI_RESET_MASK,
	       ctx->io.hci + ALICE_8895_HCI_SW_RST);
	ret = readl_poll_timeout(ctx->io.hci + ALICE_8895_HCI_SW_RST,
				 value,
				 !(value & ALICE_8895_HCI_RESET_MASK),
				 1, 1000); /* donor reset <= 1 ms */
	if (ret)
		return ret;

	/* Source donor GPIO_OUT low, 5us, high. */
	writel(0, ctx->io.hci + ALICE_8895_HCI_GPIO_OUT);
	udelay(5);
	writel(1, ctx->io.hci + ALICE_8895_HCI_GPIO_OUT);
	return 0;
}

static int alice_8895_variant_init(struct ufs_hba *hba)
{
	struct alice_8895_host *ctx = alice_8895_ctx(hba);

	/* No P23 platform probe ever populates hba->priv. */
	if (!ctx)
		return -EPERM;
	return alice_8895_prepare_power(ctx);
}

static void alice_8895_variant_exit(struct ufs_hba *hba)
{
	alice_8895_release_resources(alice_8895_ctx(hba));
}

static int alice_8895_variant_hce(struct ufs_hba *hba,
				  enum ufs_notify_change_status status)
{
	struct alice_8895_host *ctx = alice_8895_ctx(hba);

	if (!ctx || !ctx->secure_ready)
		return -EPERM;
	if (status == PRE_CHANGE)
		return alice_8895_host_reset(ctx);
	if (status == POST_CHANGE)
		return 0;
	return -EINVAL;
}

static int alice_8895_variant_link(struct ufs_hba *hba,
				   enum ufs_notify_change_status status)
{
	struct alice_8895_host *ctx = alice_8895_ctx(hba);
	int ret;

	if (!ctx || !ctx->secure_ready || !ctx->link_prepared)
		return -EPERM;
	switch (status) {
	case PRE_CHANGE:
		ret = alice_ufs8895_run_phase(&ctx->io, 0, NULL);
		if (ret)
			return ret;
		return 0;
	case POST_CHANGE:
		ret = alice_ufs8895_run_phase(&ctx->io, 1, NULL);
		if (!ret)
			ctx->link_started = true;
		return ret;
	default:
		return -EINVAL;
	}
}

static int alice_8895_variant_power(struct ufs_hba *hba,
				    enum ufs_notify_change_status status,
				    struct ufs_pa_layer_attr *max,
				    struct ufs_pa_layer_attr *requested)
{
	struct alice_8895_host *ctx = alice_8895_ctx(hba);
	struct alice_ufs8895_power p;
	unsigned int phase;
	int ret;

	if (!ctx || !ctx->link_started || !requested || !max)
		return -EPERM;
	if (!requested->lane_rx || requested->lane_rx > ctx->io.lanes ||
	    requested->lane_rx != requested->lane_tx ||
	    requested->gear_rx != requested->gear_tx ||
	    requested->lane_rx > max->lane_rx ||
	    requested->lane_tx > max->lane_tx)
		return -EINVAL;

	if (requested->pwr_rx == FAST_MODE &&
	    requested->pwr_tx == FAST_MODE) {
		p.speed = ALICE_UFS8895_HS;
		p.gear = requested->gear_rx;
		if (requested->hs_rate != PA_HS_MODE_A &&
		    requested->hs_rate != PA_HS_MODE_B)
			return -EINVAL;
		phase = requested->hs_rate == PA_HS_MODE_B ? 4 : 3;
	} else if (requested->pwr_rx == SLOW_MODE &&
		   requested->pwr_tx == SLOW_MODE) {
		p.speed = ALICE_UFS8895_PWM;
		p.gear = requested->gear_rx;
		phase = 2;
	} else {
		return -EOPNOTSUPP; /* FASTAUTO/SLOWAUTO require audit */
	}
	p.lanes = requested->lane_rx;

	ret = alice_ufs8895_check_phase(&ctx->io, phase, &p);
	if (ret)
		return ret;
	if (status == PRE_CHANGE)
		return alice_ufs8895_run_phase(&ctx->io, phase, &p);

	if (status == POST_CHANGE && p.speed == ALICE_UFS8895_HS) {
		phase = requested->hs_rate == PA_HS_MODE_B ? 6 : 5;
		return alice_ufs8895_run_phase(&ctx->io, phase, &p);
	}
	if (status == POST_CHANGE)
		return 0;
	return -EINVAL;
}

static int alice_8895_variant_clocks(struct ufs_hba *hba, bool on,
				     enum ufs_notify_change_status status)
{
	struct alice_8895_host *ctx = alice_8895_ctx(hba);

	if (!ctx || !ctx->link_started || !ctx->secure_ready)
		return -EPERM;

	/* Vendor pre_clk_off before and post_clk_on after a clock change.
	 * Clock ownership remains with Linux 5.10 UFS core; avoid double
	 * enabling / disabling clk handles in this callback.
	 */
	if (!on && status == PRE_CHANGE)
		return alice_ufs8895_run_phase(&ctx->io, 7, NULL);
	if (on && status == POST_CHANGE)
		return alice_ufs8895_run_phase(&ctx->io, 8, NULL);
	if (status == PRE_CHANGE || status == POST_CHANGE)
		return 0;
	return -EINVAL;
}

static int alice_8895_variant_suspend(struct ufs_hba *hba,
				      enum ufs_pm_op pm_op)
{
	struct alice_8895_host *ctx = alice_8895_ctx(hba);

	if (!ctx || !ctx->secure_ready)
		return -EPERM;

	/* Hardware link-state constraints are not yet verified; deliberately
	 * refuse real suspend rather than power down an active UFS link.
	 */
	return -EOPNOTSUPP;
}

static int alice_8895_variant_resume(struct ufs_hba *hba,
				     enum ufs_pm_op pm_op)
{
	struct alice_8895_host *ctx = alice_8895_ctx(hba);

	if (!ctx || !ctx->secure_ready)
		return -EPERM;

	/* Do not run FMP_RESUME until suspend/restore and ACPM ownership are
	 * verified. P22 secure_resume exists but isn't called from here.
	 */
	return -EOPNOTSUPP;
}

static const struct ufs_hba_variant_ops alice_8895_variant_ops = {
	.name = "alice-exynos8895-no-probe",
	.init = alice_8895_variant_init,
	.exit = alice_8895_variant_exit,
	.setup_clocks = alice_8895_variant_clocks,
	.hce_enable_notify = alice_8895_variant_hce,
	.link_startup_notify = alice_8895_variant_link,
	.pwr_change_notify = alice_8895_variant_power,
	.suspend = alice_8895_variant_suspend,
	.resume = alice_8895_variant_resume,
};

/* Does NOT register device, UFS host or compatible, and is never called
 * by any P23 platform initialization. API/ELF integration proof only.
 */
const struct ufs_hba_variant_ops *alice_8895_get_host_ops(void)
{
	return &alice_8895_variant_ops;
}
