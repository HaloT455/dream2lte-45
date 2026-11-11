// SPDX-License-Identifier: GPL-2.0
/*
 * Zstandard for the synchronous Crypto API.
 * Copyright (c) 2017-present, Facebook, Inc.
 * Adapted from Linux 4.19.325 for the legacy zram Crypto API.
 */

#include <linux/crypto.h>
#include <linux/init.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/vmalloc.h>
#include <linux/zstd.h>

#define ZSTD_DEF_LEVEL	1

struct zstd_ctx {
	ZSTD_CCtx *cctx;
	ZSTD_DCtx *dctx;
	ZSTD_parameters params;
	void *cworkspace;
	void *dworkspace;
};

static void zstd_exit(struct crypto_tfm *tfm)
{
	struct zstd_ctx *ctx = crypto_tfm_ctx(tfm);

	vfree(ctx->cworkspace);
	vfree(ctx->dworkspace);
}

static int zstd_init(struct crypto_tfm *tfm)
{
	struct zstd_ctx *ctx = crypto_tfm_ctx(tfm);
	size_t csize, dsize;
	int ret = -ENOMEM;

	/* zram compresses one page per request and reuses a per-CPU context. */
	ctx->params = ZSTD_getParams(ZSTD_DEF_LEVEL, PAGE_SIZE, 0);
	csize = ZSTD_CCtxWorkspaceBound(ctx->params.cParams);
	dsize = ZSTD_DCtxWorkspaceBound();

	ctx->cworkspace = vzalloc(csize);
	if (!ctx->cworkspace)
		return -ENOMEM;
	ctx->dworkspace = vzalloc(dsize);
	if (!ctx->dworkspace)
		goto out_free;

	ctx->cctx = ZSTD_initCCtx(ctx->cworkspace, csize);
	ctx->dctx = ZSTD_initDCtx(ctx->dworkspace, dsize);
	if (ctx->cctx && ctx->dctx)
		return 0;
	ret = -EINVAL;

out_free:
	zstd_exit(tfm);
	return ret;
}

static int zstd_compress(struct crypto_tfm *tfm, const u8 *src,
			 unsigned int slen, u8 *dst, unsigned int *dlen)
{
	struct zstd_ctx *ctx = crypto_tfm_ctx(tfm);
	size_t len;

	len = ZSTD_compressCCtx(ctx->cctx, dst, *dlen, src, slen, ctx->params);
	if (ZSTD_isError(len))
		return -EINVAL;
	*dlen = len;
	return 0;
}

static int zstd_decompress(struct crypto_tfm *tfm, const u8 *src,
			   unsigned int slen, u8 *dst, unsigned int *dlen)
{
	struct zstd_ctx *ctx = crypto_tfm_ctx(tfm);
	size_t len;

	len = ZSTD_decompressDCtx(ctx->dctx, dst, *dlen, src, slen);
	if (ZSTD_isError(len))
		return -EINVAL;
	*dlen = len;
	return 0;
}

static struct crypto_alg zstd_alg = {
	.cra_name		= "zstd",
	.cra_driver_name	= "zstd-generic",
	.cra_flags		= CRYPTO_ALG_TYPE_COMPRESS,
	.cra_ctxsize		= sizeof(struct zstd_ctx),
	.cra_module		= THIS_MODULE,
	.cra_init		= zstd_init,
	.cra_exit		= zstd_exit,
	.cra_u.compress		= {
		.coa_compress	= zstd_compress,
		.coa_decompress	= zstd_decompress,
	},
};

static int __init zstd_mod_init(void)
{
	return crypto_register_alg(&zstd_alg);
}

static void __exit zstd_mod_fini(void)
{
	crypto_unregister_alg(&zstd_alg);
}

module_init(zstd_mod_init);
module_exit(zstd_mod_fini);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Zstandard Compression Algorithm");
MODULE_ALIAS_CRYPTO("zstd");
