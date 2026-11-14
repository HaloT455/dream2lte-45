// SPDX-License-Identifier: GPL-2.0
/*
 * Synchronous crypto adapter for the Huawei LZ4KD codec.
 * Based on the Huawei Technologies Co., Ltd. 2022 crypto adapter.
 */

#include <linux/crypto.h>
#include <linux/init.h>
#include <linux/lz4kd.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/vmalloc.h>

static int lz4kd_init(struct crypto_tfm *tfm)
{
	void **workspace = crypto_tfm_ctx(tfm);

	*workspace = vmalloc(lz4kd_encode_state_bytes_min());
	return *workspace ? 0 : -ENOMEM;
}

static void lz4kd_exit(struct crypto_tfm *tfm)
{
	void **workspace = crypto_tfm_ctx(tfm);

	vfree(*workspace);
}

static int lz4kd_compress(struct crypto_tfm *tfm, const u8 *src,
			 unsigned int slen, u8 *dst, unsigned int *dlen)
{
	void **workspace = crypto_tfm_ctx(tfm);
	int len;

	if (slen != PAGE_SIZE)
		return -EINVAL;
	if (*dlen < 2 * PAGE_SIZE)
		return -ENOSPC;

	len = lz4kd_encode(*workspace, src, dst, slen, *dlen, slen);
	if (len < 0)
		return -EINVAL;
	if (!len || len >= slen) {
		/* A full-size result lets zram store this page uncompressed. */
		memcpy(dst, src, slen);
		len = slen;
	}
	*dlen = len;
	return 0;
}

static int lz4kd_decompress(struct crypto_tfm *tfm, const u8 *src,
			   unsigned int slen, u8 *dst, unsigned int *dlen)
{
	int len;

	if (*dlen < PAGE_SIZE)
		return -ENOSPC;
	if (slen == PAGE_SIZE) {
		memcpy(dst, src, PAGE_SIZE);
	} else {
		if (slen > PAGE_SIZE)
			return -EINVAL;
		len = lz4kd_decode(src, dst, slen, PAGE_SIZE);
		if (len != PAGE_SIZE)
			return -EINVAL;
	}
	*dlen = PAGE_SIZE;
	return 0;
}

static struct crypto_alg lz4kd_alg = {
	.cra_name = "lz4kd",
	.cra_driver_name = "lz4kd-generic",
	.cra_flags = CRYPTO_ALG_TYPE_COMPRESS,
	.cra_ctxsize = sizeof(void *),
	.cra_module = THIS_MODULE,
	.cra_init = lz4kd_init,
	.cra_exit = lz4kd_exit,
	.cra_u.compress = {
		.coa_compress = lz4kd_compress,
		.coa_decompress = lz4kd_decompress,
	},
};

static int __init lz4kd_mod_init(void)
{
	return crypto_register_alg(&lz4kd_alg);
}

static void __exit lz4kd_mod_fini(void)
{
	crypto_unregister_alg(&lz4kd_alg);
}

module_init(lz4kd_mod_init);
module_exit(lz4kd_mod_fini);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("LZ4KD page compression");
MODULE_ALIAS_CRYPTO("lz4kd");
