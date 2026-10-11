// SPDX-License-Identifier: GPL-2.0
/*
 * Exynos8895 UFS firmware commands from pinned Samsung donor smc.h.
 * Uses native Linux 5.10 SMCCC transport instead of missing exynos_smc().
 *
 * NO CLIENT, NO PROBE, NO BOOT: firmware calls are denied by default.
 * This is not a validated runtime ABI conversion. The real secure firmware
 * return-code conventions and encryption state require physical validation.
 */
#include <linux/arm-smccc.h>
#include <linux/errno.h>
#include <linux/kernel.h>
#include "alice-ufs8895-smc.h"

static int alice_8895_ufs_call(struct alice_8895_smc_ctx *ctx,
			      unsigned long command, unsigned long arg1,
			      unsigned long arg2, unsigned long arg3)
{
	struct arm_smccc_res res;

	if (!ctx || !ctx->enable_firmware_calls ||
	    !ctx->firmware_abi_verified || !ctx->ufs_power_verified)
		return -EPERM;
	if (command != ALICE_8895_SMC_FMP_SECURITY &&
	    command != ALICE_8895_SMC_SMU &&
	    command != ALICE_8895_SMC_FMP_RESUME &&
	    command != ALICE_8895_SMC_LOG)
		return -EINVAL;

	arm_smccc_smc(command, arg1, arg2, arg3, 0, 0, 0, 0, &res);
	/*
	 * Original exynos_smc() forwarded x0 as signed return code.
	 * A zero return is the only known-success state accepted here;
	 * preserve raw errors by failing closed instead of ignoring them.
	 */
	if ((long)res.a0)
		return -EIO;
	return 0;
}

int alice_8895_ufs_secure_init(struct alice_8895_smc_ctx *ctx,
			      bool fmp_ufs_enabled)
{
	int ret;

	if (!ctx)
		return -EINVAL;
	ctx->smu_ready = false;
	ctx->fmp_ready = false;

	ret = alice_8895_ufs_call(ctx, ALICE_8895_SMC_FMP_SECURITY,
				 0, ALICE_8895_FMP_UFS_MMC,
				 fmp_ufs_enabled ? ALICE_8895_DESCTYPE_3 :
						   ALICE_8895_DESCTYPE_0);
	if (ret)
		return ret;
	ctx->fmp_ready = true;

	ret = alice_8895_ufs_call(ctx, ALICE_8895_SMC_SMU,
				 ALICE_8895_SMU_INIT,
				 ALICE_8895_FMP_UFS_MMC, 0);
	if (ret) {
		ctx->fmp_ready = false;
		return ret;
	}
	ctx->smu_ready = true;
	return 0;
}

int alice_8895_ufs_secure_resume(struct alice_8895_smc_ctx *ctx,
				bool fmp_ufs_enabled)
{
	int ret;

	ret = alice_8895_ufs_secure_init(ctx, fmp_ufs_enabled);
	if (ret)
		return ret;

	if (!fmp_ufs_enabled)
		return 0;
	ret = alice_8895_ufs_call(ctx, ALICE_8895_SMC_FMP_RESUME,
				 0, ALICE_8895_FMP_UFS_MMC, 0);
	if (ret) {
		ctx->smu_ready = false;
		ctx->fmp_ready = false;
	}
	return ret;
}

int alice_8895_ufs_secure_log(struct alice_8895_smc_ctx *ctx)
{
	if (!ctx)
		return -EINVAL;
	if (!ctx->smu_ready || !ctx->fmp_ready)
		return -EPERM;
	return alice_8895_ufs_call(ctx, ALICE_8895_SMC_LOG, 0, 0, 2);
}
