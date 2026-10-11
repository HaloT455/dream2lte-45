/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Exynos8895 P23: unregistered Linux 5.10 host variant integration LAB.
 * Hardware state never becomes eligible without explicit verified binding.
 */
#ifndef _ALICE_8895_UFS_HOST_H_
#define _ALICE_8895_UFS_HOST_H_
#include <linux/clk.h>
#include <linux/io.h>
#include <linux/regmap.h>
#include <linux/regulator/consumer.h>
#include "alice-ufs8895-engine.h"
#include "alice-ufs8895-smc.h"

struct ufs_hba;
struct ufs_hba_variant_ops;

/*
 * VCC in pinned 8895 DTS: regulator-fixed ufs-vcc on gpg0[0],
 * regulator-boot-on. Do NOT equate to an S2MPS17 output rail.
 * PMU isolation register is 0x16480724, separately mapped.
 */
struct alice_8895_host {
	u32 signature;
	bool allow_hardware;
	bool board_resources_verified;
	bool acpm_firmware_verified;
	bool speedy_pmic_verified;
	bool vcc_gpio_mapping_verified;
	bool clock_ownership_verified;
	bool pmu_isolation_verified;
	bool sysreg_ownership_verified;
	bool secure_firmware_verified;
	bool fmp_ufs_enabled;
	struct regulator *vcc;
	struct clk *hci_clk;
	struct clk *unipro_clk;
	struct regmap *pmu;
	void __iomem *phy_isolation;
	void __iomem *sys_coherency;
	void __iomem *sys_tcxo;
	struct alice_ufs8895_hw io;
	struct alice_8895_smc_ctx smc;
	bool vcc_owned;
	bool hci_clk_owned;
	bool unipro_clk_owned;
	bool link_prepared;
	bool secure_ready;
	bool link_started;
};

#define ALICE_8895_HOST_SIGNATURE 0x88952310U

/* Validation has no MMIO, no GPIO, no regulator writes and no firmware call. */
int alice_8895_host_validate(const struct alice_8895_host *ctx);

/*
 * Strictly unregistered: no platform driver, no of_match, no probe.
 * Returning the table does not attach it to Linux UFS core.
 */
const struct ufs_hba_variant_ops *alice_8895_get_host_ops(void);
#endif
