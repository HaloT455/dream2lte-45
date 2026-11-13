/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2022. All rights reserved.
 * Description: LZ4K compression algorithm with delta compression
 */

#if !defined(__KERNEL__)
#include "lz4kd.h"
#else
#include <linux/lz4kd.h>
#include <linux/module.h>
#endif

#include "lz4kd_private.h" /* types, etc */

static const uint8_t *get_size(
	uint_fast32_t *size,
	const uint8_t *in_at,
	const uint8_t *const in_end)
{
	uint_fast32_t u;
	do {
		if (unlikely(in_at >= in_end))
			return NULL;
		*size += (u = *(const uint8_t*)in_at);
		++in_at;
	} while (BYTE_MAX == u);
	return in_at;
}

static int end_of_block(
	const uint_fast32_t nr_bytes_max,
	const uint_fast32_t r_bytes_max,
	const uint8_t *const in_at,
	const uint8_t *const in_end,
	const uint8_t *const out,
	const uint8_t *const out_at)
{
	if (!nr_bytes_max)
		return LZ4K_STATUS_FAILED; /* should be the last one in block */
	if (r_bytes_max != REPEAT_MIN)
		return LZ4K_STATUS_FAILED; /* should be the last one in block */
	if (in_at != in_end)
		return LZ4K_STATUS_FAILED; /* should be the last one in block */
	return (int)(out_at - out);
}

enum {
	NR_COPY_MIN = 16,
	R_COPY_MIN = 16,
	R_COPY_SAFE_2X = (R_COPY_MIN << 1) - 1
};

static bool out_non_repeat(
	const uint8_t **in_at,
	uint8_t **out_at,
	uint_fast32_t nr_bytes_max,
	const uint8_t *const in_end,
	const uint8_t *const out_end)
{
	const uint8_t *in_copy_end;
	uint8_t *out_copy_end;

	if (unlikely(nr_bytes_max > (size_t)(in_end - *in_at) ||
		     nr_bytes_max > (size_t)(out_end - *out_at)))
		return false;

	in_copy_end = *in_at + nr_bytes_max;
	out_copy_end = *out_at + nr_bytes_max;
	if (likely(nr_bytes_max <= NR_COPY_MIN)) {
		if (likely(in_end - *in_at >= NR_COPY_MIN &&
			   out_end - *out_at >= NR_COPY_MIN))
			m_copy(*out_at, *in_at, NR_COPY_MIN);
		else
			m_copy(*out_at, *in_at, nr_bytes_max);
	} else { /* nr_bytes_max>NR_COPY_MIN */
		if (likely(in_end - in_copy_end >= NR_COPY_MIN &&
			   out_end - out_copy_end >= NR_COPY_MIN)) {
			m_copy(*out_at, *in_at, NR_COPY_MIN);
			copy_x_while_lt(*out_at + NR_COPY_MIN,
					*in_at + NR_COPY_MIN,
					out_copy_end, NR_COPY_MIN);
		} else
			m_copy(*out_at, *in_at, nr_bytes_max);
	} /* if (nr_bytes_max <= NR_COPY_MIN) */
	*in_at = in_copy_end;
	*out_at = out_copy_end;
	return true;
}

static void out_repeat_overlap(
	uint8_t *out_at,
	const uint8_t *out_from,
	const uint8_t *const out_copy_end)
{
	/* Expand the pattern using only bytes already written to the page. */
	while (out_at < out_copy_end && out_at - out_from < R_COPY_MIN) {
		size_t copy = min_u64(out_at - out_from, out_copy_end - out_at);

		m_copy(out_at, out_from, copy);
		out_at += copy;
	}
	while_lt_copy_2x_as_x2(out_at, out_from, out_copy_end, R_COPY_MIN);
}

static int decode(
	const uint8_t *in_at,
	uint8_t *const out,
	const uint8_t *const in_end,
	const uint8_t *const out_end,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{
	const uint_fast32_t r_log2 = TAG_BITS_MAX - (off_log2 + nr_log2);
	const uint8_t *const in_end_minus_x = in_end - TAG_BYTES_MAX;
	uint8_t *out_at = out;
	while (likely(in_at <= in_end_minus_x)) {
		const uint_fast32_t utag = read4_at(in_at - 1) >> BYTE_BITS;
		const uint_fast32_t offset = utag & mask(off_log2);
		uint_fast32_t nr_bytes_max = utag >> (off_log2 + r_log2),
			      r_bytes_max = ((utag >> off_log2) & mask(r_log2)) +
					    REPEAT_MIN;
		const uint8_t *out_from;
		uint8_t *out_copy_end;
		in_at += TAG_BYTES_MAX;
		if (unlikely(nr_bytes_max == mask(nr_log2))) {
			in_at = get_size(&nr_bytes_max, in_at, in_end);
			if (unlikely(in_at == NULL))
				return LZ4K_STATUS_READ_ERROR;
		}
		if (!out_non_repeat(&in_at, &out_at, nr_bytes_max, in_end, out_end))
			return LZ4K_STATUS_FAILED;
		if (unlikely(r_bytes_max == mask(r_log2) + REPEAT_MIN)) {
			in_at = get_size(&r_bytes_max, in_at, in_end);
			if (unlikely(in_at == NULL))
				return LZ4K_STATUS_READ_ERROR;
		}
		if (unlikely(!offset))
			return end_of_block(nr_bytes_max, r_bytes_max, in_at,
					    in_end, out, out_at);
		if (unlikely(offset > (size_t)(out_at - out) ||
			     r_bytes_max > (size_t)(out_end - out_at)))
			return LZ4K_STATUS_FAILED;

		out_from = out_at - offset;
		out_copy_end = out_at + r_bytes_max;
		if (offset == 1) {
			m_set(out_at, *out_from, r_bytes_max);
		} else if (out_end - out_copy_end >= R_COPY_SAFE_2X) {
			if (offset >= R_COPY_MIN)
				copy_2x_as_x2_while_lt(out_at, out_from, out_copy_end,
						       R_COPY_MIN);
			else
				out_repeat_overlap(out_at, out_from, out_copy_end);
		} else {
			while (out_at < out_copy_end)
				*out_at++ = *out_from++;
		}
		out_at = out_copy_end;
	} /* while (likely(in_at <= in_end_minus_x)) */
	return in_at == in_end ? (int)(out_at - out) : LZ4K_STATUS_FAILED;
}

static int decode_pattern_4kb(
	const uint8_t *const in,
	uint8_t *const out,
	const uint8_t *const out_end)
{
	const uint64_t pattern = read8_at(in);
	uint8_t *pos;

	for (pos = out; pos < out_end; pos += sizeof(pattern))
		m_copy(pos, &pattern, sizeof(pattern));
	return out_end - out;
}

static int decode_4kb(
	const uint8_t *const in,
	uint8_t *const out,
	const uint8_t *const in_end,
	const uint8_t *const out_end)
{
	return decode(in, out, in_end, out_end, NR_4KB_LOG2, BLOCK_4KB_LOG2);
}

int lz4kd_decode(
	const void *in,
	void *const out,
	unsigned in_max,
	unsigned out_max)
{
	/* ++use volatile pointers to prevent compiler optimizations */
	const uint8_t *volatile in_end = (const uint8_t*)in + in_max;
	const uint8_t *volatile out_end = (uint8_t*)out + min_u64(out_max, 1 << BLOCK_4KB_LOG2);
	if (unlikely(in == NULL || out == NULL))
		return LZ4K_STATUS_FAILED;
	if (unlikely(in_max <= 1 + TAG_BYTES_MAX ||
		     in_max >= (1 << BLOCK_4KB_LOG2) ||
		     out_max < (1 << BLOCK_4KB_LOG2)))
		return LZ4K_STATUS_FAILED;
	/* invalid buffer size or pointer overflow */
	if (unlikely((const uint8_t*)in >= in_end || (uint8_t*)out >= out_end))
		return LZ4K_STATUS_FAILED;
	/* -- */
	if (unlikely(in_max == PATTERN_BYTES_MAX))
		return decode_pattern_4kb((const uint8_t*)in, (uint8_t*)out,
				out_end);
	if (unlikely(*(const uint8_t *)in != 0))
		return LZ4K_STATUS_FAILED;
	return decode_4kb((const uint8_t*)in + 1, (uint8_t*)out, in_end, out_end);
}
EXPORT_SYMBOL(lz4kd_decode);

MODULE_LICENSE("Dual BSD/GPL");
MODULE_DESCRIPTION("LZ4K decoder");
