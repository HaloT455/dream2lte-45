/* SPDX-License-Identifier: GPL-2.0 */
/* P22 Exynos8895 Samsung UFS secure monitor ABI bridge, NOT BOOTABLE. */
#ifndef _ALICE_8895_UFS_SECURE_H
#define _ALICE_8895_UFS_SECURE_H
#include <linux/types.h>

/* Same raw IDs as pinned Samsung 4.4 include/linux/smc.h. */
#define ALICE_8895_SMC_FMP_SECURITY 0xC2001810U
#define ALICE_8895_SMC_FMP_DISKENC  0xC2001820U
#define ALICE_8895_SMC_SMU          0xC2001830U
#define ALICE_8895_SMC_LOG          0xC2001860U

#define ALICE_8895_FMP_UFS_MMC      0U
#define ALICE_8895_SMU_INIT         0U
#define ALICE_8895_FMP_DESC_PLAIN   0U
#define ALICE_8895_FMP_DESC_CRYPTO  3U

struct alice_ufs8895_secure {
	/* All gates default to false. P22 supplies no hardware caller. */
	bool secure_firmware_abi_verified;
	bool original_prdt_layout_verified;
	bool original_disk_key_path_verified;
	bool allow_smc_io;
	bool secure_storage_ready;
	u32 descriptor_type; /* 0 or 3, exact original #ifdef CONFIG_FMP_UFS */
	s32 last_firmware_status; /* 32-bit w0 from ARM64 SMC, not generic errno */
};

/*
 * Calls real Samsung firmware SMC using genuine Linux 5.10 arm_smccc_smc,
 * but only with ALL prerequisites explicitly verified; return -EPERM
 * without firmware operations otherwise. Does not itself enable UFS.
 */
int alice_ufs8895_secure_storage_init(struct alice_ufs8895_secure *ctx);

/* Exact Samsung secure-log command from original host-reset path. */
int alice_ufs8895_secure_log_reset(struct alice_ufs8895_secure *ctx);
#endif
