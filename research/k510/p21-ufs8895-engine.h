/* SPDX-License-Identifier: GPL-2.0 */
/* P21 Exynos8895 UFS PHY/UniPro calibration engine, NO-FLASH research. */
#ifndef _ALICE_8895_UFS_CAL_ENGINE_H
#define _ALICE_8895_UFS_CAL_ENGINE_H

#include <linux/io.h>
#include <linux/types.h>

struct ufs_hba;

enum alice_ufs8895_speed {
	ALICE_UFS8895_PWM = 0,
	ALICE_UFS8895_HS = 1,
};

struct alice_ufs8895_power {
	enum alice_ufs8895_speed speed;
	u8 gear;
	u8 lanes;
};

/*
 * Not populated by any driver in P21. The caller must separately establish
 * ACPM/S2MPS17 power, clocks and the FMP/SMC secure-storage prerequisites.
 */
struct alice_ufs8895_hw {
	struct ufs_hba *hba;
	void __iomem *pma;
	void __iomem *unipro;
	void __iomem *hci;
	u32 pma_bytes;
	u32 unipro_bytes;
	u32 hci_bytes;
	u32 mclk_hz;
	u32 pclk_hz;
	u8 lanes; /* physical lanes: 1 or 2 */
	bool allow_hardware_io; /* defaults false; never enabled by P21 */
};

/* NULL power matches original Samsung donor's NULL pmd: unconditional. */
int alice_ufs8895_check_phase(const struct alice_ufs8895_hw *hw,
			      unsigned int phase,
			      const struct alice_ufs8895_power *power);

/* Returns -EPERM with default unauthorized context; no P21 caller exists. */
int alice_ufs8895_run_phase(struct alice_ufs8895_hw *hw,
			    unsigned int phase,
			    const struct alice_ufs8895_power *power);
#endif
