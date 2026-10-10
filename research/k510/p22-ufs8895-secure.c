// SPDX-License-Identifier: GPL-2.0
/*
 * Linux 5.10 ARM64 Exynos8895 Secure Monitor transition.
 * Original __exynos_smc: dsb sy; smc #0; return x0 as int.
 * Original UFS sequence: SMC_CMD_FMP_SECURITY, then SMC_CMD_SMU.
 * No noop stubs, no re-encoding of secure firmware command or arguments.
 */
#include <linux/arm-smccc.h>
#include <linux/errno.h>
#include <linux/kernel.h>
#include <asm/barrier.h>
#include "alice-ufs8895-secure.h"

/*
 * Linux arm_smccc_smc uses identical x0..x3 register argument positions,
 * and returns raw x0. There is NO SMCCC -> Linux errno equivalence for
 * Samsung firmware proprietary errors: retain exact raw status.
 */
static int alice_8895_issue_smc(struct alice_ufs8895_secure *ctx,
				u32 command, u32 arg1, u32 arg2, u32 arg3)
{
	struct arm_smccc_res result;

	dsb(sy);
	arm_smccc_smc(command, arg1, arg2, arg3, 0, 0, 0, 0, &result);
	ctx->last_firmware_status = (s32)(u32)result.a0;
	if (ctx->last_firmware_status)
		return -EIO;
	return 0;
}

static bool alice_8895_verified(const struct alice_ufs8895_secure *ctx)
{
	return ctx && ctx->secure_firmware_abi_verified &&
	       ctx->original_prdt_layout_verified &&
	       ctx->original_disk_key_path_verified &&
	       ctx->allow_smc_io;
}

int alice_ufs8895_secure_storage_init(struct alice_ufs8895_secure *ctx)
{
	int ret;

	if (!ctx)
		return -EINVAL;
	/* Reset state before attempting either firmware operation. */
	ctx->secure_storage_ready = false;
	ctx->last_firmware_status = 0;

	if (!alice_8895_verified(ctx))
		return -EPERM;
	if (ctx->descriptor_type != ALICE_8895_FMP_DESC_PLAIN &&
	    ctx->descriptor_type != ALICE_8895_FMP_DESC_CRYPTO)
		return -EINVAL;

	/*
	 * Original UFS driver: exynos_smc(SMC_CMD_FMP_SECURITY,
	 *            0, ID_FMP_UFS_MMC, FMP_DESCTYPE_0|3).
	 * Descriptor 3 must ONLY be selected for verified CONFIG_FMP_UFS
	 * and the corresponding Samsung encryption-capable PRDT layout.
	 */
	ret = alice_8895_issue_smc(ctx, ALICE_8895_SMC_FMP_SECURITY,
				   0, ALICE_8895_FMP_UFS_MMC,
				   ctx->descriptor_type);
	if (ret)
		return ret;

	/* Original: exynos_smc(SMC_CMD_SMU, FMP_SMU_INIT, ID_FMP_UFS_MMC, 0). */
	ret = alice_8895_issue_smc(ctx, ALICE_8895_SMC_SMU,
				   ALICE_8895_SMU_INIT,
				   ALICE_8895_FMP_UFS_MMC, 0);
	if (ret)
		return ret;

	ctx->secure_storage_ready = true;
	return 0;
}

int alice_ufs8895_secure_log_reset(struct alice_ufs8895_secure *ctx)
{
	if (!alice_8895_verified(ctx) || !ctx->secure_storage_ready)
		return -EPERM;

	/* Original ufs_exynos host-reset path: exynos_smc(SMC_CMD_LOG,0,0,2) */
	return alice_8895_issue_smc(ctx, ALICE_8895_SMC_LOG, 0, 0, 2);
}
