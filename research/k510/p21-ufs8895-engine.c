// SPDX-License-Identifier: GPL-2.0
/*
 * P21 Linux 5.10 Exynos8895 calibration executor (compiled, NEVER PROBED).
 *
 * Donor: exact V12R5T ufs-exynos.c config_uic(), wait_*_lock() and
 * ufs-exynos.h (PMA address and clock-stop register semantics).
 * No of_match, probe, platform driver or client; SMC/FMP/PMIC not ported.
 */
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/jiffies.h>
#include <linux/kernel.h>
#include <linux/time64.h>
#include "ufshcd.h"
#include "ufshci.h"
#include "unipro.h"
#include "alice-ufs8895-calibration.h"
#include "alice-ufs8895-engine.h"

#define ALICE_8895_CLKSTOP_CTRL		0xb0U
#define ALICE_8895_MPHY_APBCLK_STOP	BIT(3)
#define ALICE_8895_PLL_CDR_TIMEOUT_MS	100U
#define ALICE_8895_RX_LANE0		4U
#define ALICE_8895_MAX_LANES		2U

/* Original 4.4 ufs-exynos.h mode bits, not Linux 5.10 Exynos7 modes. */
#define ALICE_8895_PMD_ALL	(BIT(15) - 1U)
#define ALICE_8895_PMD_PWM	(BIT(7) - 1U)
#define ALICE_8895_PMD_HS	(ALICE_8895_PMD_ALL ^ ALICE_8895_PMD_PWM)

static bool alice_8895_mode_matches(const struct alice_ufs8895_power *p,
				    u32 mask)
{
	unsigned int bit;

	if (!p || mask == ALICE_8895_PMD_ALL)
		return true;
	if (p->speed == ALICE_UFS8895_PWM && mask == ALICE_8895_PMD_PWM)
		return true;
	if (p->speed == ALICE_UFS8895_HS && mask == ALICE_8895_PMD_HS)
		return true;

	bit = ((p->speed == ALICE_UFS8895_HS) ? 10U : 0U) +
		(p->gear - 1U) * 2U + (p->lanes - 1U);
	return !!(mask & BIT(bit));
}

/* Complete preflight before issuing a single MMIO or UIC request. */
static int alice_8895_check_table(const struct alice_ufs8895_hw *hw,
				  const struct alice_ufs8895_cal_table *table,
				  const struct alice_ufs8895_power *power)
{
	unsigned int i;
	const struct alice_ufs8895_cal_entry *e;
	u32 upper;

	if (!hw || !table || !hw->hba || !hw->pma || !hw->hci ||
	    !hw->unipro || !hw->lanes ||
	    hw->lanes > ALICE_8895_MAX_LANES ||
	    !hw->mclk_hz || !hw->pclk_hz ||
	    hw->mclk_hz > NSEC_PER_SEC || hw->pclk_hz > NSEC_PER_SEC ||
	    hw->pma_bytes < sizeof(u32) ||
	    hw->unipro_bytes < sizeof(u32) ||
	    hw->hci_bytes < ALICE_8895_CLKSTOP_CTRL + sizeof(u32))
		return -EINVAL;

	if (power && ((power->speed != ALICE_UFS8895_PWM &&
		       power->speed != ALICE_UFS8895_HS) ||
		      !power->lanes || power->lanes > hw->lanes ||
		      !power->gear ||
		      power->gear > (power->speed == ALICE_UFS8895_HS ?
				     3U : 5U)))
		return -EINVAL;

	for (i = 0; i < table->count; ++i) {
		e = &table->entries[i];
		if (!alice_8895_mode_matches(power, e->power_mode_mask))
			continue;

		switch (e->space) {
		case ALICE_8895_PHY_PCS_COMN:
		case ALICE_8895_PHY_PCS_RXTX:
		case ALICE_8895_PHY_PCS_RX:
		case ALICE_8895_PHY_PCS_TX:
		case ALICE_8895_PHY_PCS_RX_PRD:
		case ALICE_8895_PHY_PCS_TX_PRD:
		case ALICE_8895_UNIPRO_STD_MIB:
		case ALICE_8895_UNIPRO_DBG_MIB:
		case ALICE_8895_UNIPRO_DBG_PRD:
			if (e->address > 0xffffU)
				return -ERANGE;
			break;
		case ALICE_8895_PHY_PMA_COMN:
		case ALICE_8895_PHY_PLL_WAIT:
			if (e->address > hw->pma_bytes - sizeof(u32))
				return -ERANGE;
			break;
		case ALICE_8895_PHY_PMA_TRSV:
		case ALICE_8895_PHY_CDR_WAIT:
		case ALICE_8895_PHY_PMA_TRSV_LANE1_SQ_OFF:
			upper = hw->pma_bytes - sizeof(u32);
			if (e->address > upper ||
			    (hw->lanes - 1U) >
			     (upper - e->address) /
			     ALICE_UFS8895_PHY_LANE_STRIDE)
				return -ERANGE;
			break;
		case ALICE_8895_UNIPRO_DBG_APB:
			if ((e->address & 3U) ||
			    e->address > hw->unipro_bytes - sizeof(u32))
				return -ERANGE;
			break;
		case ALICE_8895_COMMON_WAIT:
			if (e->value > 1000000U)
				return -ERANGE;
			break;
		default:
			return -EOPNOTSUPP; /* never silently drop an opcode */
		}
	}
	return 0;
}

int alice_ufs8895_check_phase(const struct alice_ufs8895_hw *hw,
			      unsigned int phase,
			      const struct alice_ufs8895_power *power)
{
	const struct alice_ufs8895_cal_table *t =
		alice_ufs8895_get_calibration(phase);

	if (!t)
		return -EINVAL;
	return alice_8895_check_table(hw, t, power);
}

/*
 * Donor 4.4 specifically ungates MPHY_APBCLK_STOP for each PMA access,
 * then forces stop again. NOT the generic Linux 5.10 exynos7 PHY path.
 * Requires exclusive HCI/clock ownership from future real driver.
 */
static u32 alice_8895_pma_read(struct alice_ufs8895_hw *hw, u32 reg)
{
	u32 clk = readl(hw->hci + ALICE_8895_CLKSTOP_CTRL);
	u32 result;

	writel(clk & ~ALICE_8895_MPHY_APBCLK_STOP,
	       hw->hci + ALICE_8895_CLKSTOP_CTRL);
	result = readl(hw->pma + reg);
	writel(clk | ALICE_8895_MPHY_APBCLK_STOP,
	       hw->hci + ALICE_8895_CLKSTOP_CTRL);
	return result;
}

static void alice_8895_pma_write(struct alice_ufs8895_hw *hw,
				u32 reg, u32 value)
{
	u32 clk = readl(hw->hci + ALICE_8895_CLKSTOP_CTRL);

	writel(clk & ~ALICE_8895_MPHY_APBCLK_STOP,
	       hw->hci + ALICE_8895_CLKSTOP_CTRL);
	writel(value, hw->pma + reg);
	writel(clk | ALICE_8895_MPHY_APBCLK_STOP,
	       hw->hci + ALICE_8895_CLKSTOP_CTRL);
}

static int alice_8895_wait_lock(struct alice_ufs8895_hw *hw, u32 reg,
				u32 mask)
{
	unsigned long until = jiffies +
		msecs_to_jiffies(ALICE_8895_PLL_CDR_TIMEOUT_MS);

	do {
		if ((alice_8895_pma_read(hw, reg) & mask) == mask)
			return 0;
		usleep_range(1, 2);
	} while (time_before(jiffies, until));

	return -ETIMEDOUT;
}

static int alice_8895_apply_entry(struct alice_ufs8895_hw *hw,
				  const struct alice_ufs8895_cal_entry *e)
{
	unsigned int lane;
	u32 sel, value, off;
	int ret;

	for (lane = 0; lane < hw->lanes; ++lane) {
		sel = lane;
		value = e->value;

		switch (e->space) {
		case ALICE_8895_PHY_PCS_COMN:
		case ALICE_8895_UNIPRO_STD_MIB:
		case ALICE_8895_UNIPRO_DBG_MIB:
			if (lane)
				break;
			ret = ufshcd_dme_set(hw->hba,
					    UIC_ARG_MIB(e->address), value);
			if (ret)
				return ret;
			break;
		case ALICE_8895_PHY_PCS_RXTX:
			ret = ufshcd_dme_set(hw->hba,
					UIC_ARG_MIB_SEL(e->address, sel), value);
			if (ret)
				return ret;
			break;
		case ALICE_8895_PHY_PCS_RX:
		case ALICE_8895_PHY_PCS_RX_PRD:
			sel += ALICE_8895_RX_LANE0;
			fallthrough;
		case ALICE_8895_PHY_PCS_TX:
		case ALICE_8895_PHY_PCS_TX_PRD:
			if (e->space == ALICE_8895_PHY_PCS_RX_PRD ||
			    e->space == ALICE_8895_PHY_PCS_TX_PRD)
				value = NSEC_PER_SEC / hw->pclk_hz;
			ret = ufshcd_dme_set(hw->hba,
					UIC_ARG_MIB_SEL(e->address, sel), value);
			if (ret)
				return ret;
			break;
		case ALICE_8895_UNIPRO_DBG_PRD:
			if (lane)
				break;
			ret = ufshcd_dme_set(hw->hba,
					UIC_ARG_MIB(e->address),
					NSEC_PER_SEC / hw->mclk_hz);
			if (ret)
				return ret;
			break;
		case ALICE_8895_PHY_PMA_COMN:
			if (!lane)
				alice_8895_pma_write(hw, e->address, value);
			break;
		case ALICE_8895_PHY_PMA_TRSV:
			off = e->address +
				lane * ALICE_UFS8895_PHY_LANE_STRIDE;
			alice_8895_pma_write(hw, off, value);
			break;
		case ALICE_8895_PHY_PMA_TRSV_LANE1_SQ_OFF:
			if (lane == 1) {
				off = e->address +
					lane * ALICE_UFS8895_PHY_LANE_STRIDE;
				alice_8895_pma_write(hw, off, value);
			}
			break;
		case ALICE_8895_UNIPRO_DBG_APB:
			if (!lane)
				writel(value, hw->unipro + e->address);
			break;
		case ALICE_8895_PHY_PLL_WAIT:
			if (!lane) {
				ret = alice_8895_wait_lock(hw, e->address, value);
				if (ret)
					return ret;
			}
			break;
		case ALICE_8895_PHY_CDR_WAIT:
			if (!lane) {
				ret = alice_8895_wait_lock(hw, e->address, value);
				if (ret)
					return ret;
			}
			break;
		case ALICE_8895_COMMON_WAIT:
			if (!lane)
				udelay(value);
			break;
		default:
			return -EOPNOTSUPP;
		}
	}
	return 0;
}

/*
 * Deliberate hardware gate: no P21 caller can set allow_hardware_io.
 * Do not promote this to a device callback before secure storage and PMIC
 * initialization are audited; compile/link != runtime safety.
 */
int alice_ufs8895_run_phase(struct alice_ufs8895_hw *hw,
			    unsigned int phase,
			    const struct alice_ufs8895_power *power)
{
	const struct alice_ufs8895_cal_table *table =
		alice_ufs8895_get_calibration(phase);
	unsigned int i;
	int ret;

	if (!table)
		return -EINVAL;
	ret = alice_8895_check_table(hw, table, power);
	if (ret)
		return ret;
	if (!hw->allow_hardware_io)
		return -EPERM;

	for (i = 0; i < table->count; ++i) {
		const struct alice_ufs8895_cal_entry *e = &table->entries[i];

		if (!alice_8895_mode_matches(power, e->power_mode_mask))
			continue;
		ret = alice_8895_apply_entry(hw, e);
		if (ret)
			return ret;
	}
	return 0;
}
