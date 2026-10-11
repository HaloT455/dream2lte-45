/* SPDX-License-Identifier: GPL-2.0 */
/* Exynos8895 UFS firmware bridge, inactive until verified. */
#ifndef _ALICE_8895_UFS_SMC_H_
#define _ALICE_8895_UFS_SMC_H_
#include <linux/types.h>

#define ALICE_8895_SMC_FMP_SECURITY 0xC2001810UL
#define ALICE_8895_SMC_SMU          0xC2001830UL
#define ALICE_8895_SMC_FMP_RESUME   0xC2001840UL
#define ALICE_8895_SMC_LOG          0xC2001860UL
#define ALICE_8895_FMP_UFS_MMC      0UL
#define ALICE_8895_DESCTYPE_0      0UL
#define ALICE_8895_DESCTYPE_3      3UL
#define ALICE_8895_SMU_INIT        0UL

/*
 * Not connected to any driver in P22. Caller must verify secure firmware,
 * SCP/ACPM, UFS rails, encryption mode, and secure call results.
 */
struct alice_8895_smc_ctx {
	bool enable_firmware_calls;
	bool firmware_abi_verified;
	bool ufs_power_verified;
	bool smu_ready;
	bool fmp_ready;
};

int alice_8895_ufs_secure_init(struct alice_8895_smc_ctx *ctx,
			      bool fmp_ufs_enabled);
int alice_8895_ufs_secure_resume(struct alice_8895_smc_ctx *ctx,
				bool fmp_ufs_enabled);
int alice_8895_ufs_secure_log(struct alice_8895_smc_ctx *ctx);
#endif
