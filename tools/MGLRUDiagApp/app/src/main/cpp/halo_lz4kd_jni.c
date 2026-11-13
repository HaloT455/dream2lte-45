#include <jni.h>
#include <stdint.h>

#include "lz4kd.h"

#define PAGE_BYTES 4096

static jbyteArray byte_array(JNIEnv *env, const uint8_t *data, int len)
{
    jbyteArray result = (*env)->NewByteArray(env, len);
    if (result)
        (*env)->SetByteArrayRegion(env, result, 0, len, (const jbyte *)data);
    return result;
}

JNIEXPORT jbyteArray JNICALL
Java_com_halo_mglrudiag_HaloLz4kd_compress(JNIEnv *env, jclass codec, jbyteArray page)
{
    uint8_t input[PAGE_BYTES], output[2 * PAGE_BYTES];
    uint16_t workspace[PAGE_BYTES];
    int len;

    (void)codec;
    if ((*env)->GetArrayLength(env, page) != PAGE_BYTES)
        return NULL;
    (*env)->GetByteArrayRegion(env, page, 0, PAGE_BYTES, (jbyte *)input);
    if ((*env)->ExceptionCheck(env))
        return NULL;

    if (lz4kd_encode_state_bytes_min() > sizeof(workspace))
        return NULL;
    len = lz4kd_encode(workspace, input, output, PAGE_BYTES, sizeof(output), PAGE_BYTES);
    if (len < 0)
        return NULL;
    if (!len || len >= PAGE_BYTES)
        return byte_array(env, input, PAGE_BYTES);
    return byte_array(env, output, len);
}

JNIEXPORT jbyteArray JNICALL
Java_com_halo_mglrudiag_HaloLz4kd_decompress(JNIEnv *env, jclass codec, jbyteArray block)
{
    uint8_t input[PAGE_BYTES], output[PAGE_BYTES];
    jsize len = (*env)->GetArrayLength(env, block);

    (void)codec;
    if (len == PAGE_BYTES)
        return block;
    if (len <= 0 || len > PAGE_BYTES)
        return NULL;
    (*env)->GetByteArrayRegion(env, block, 0, len, (jbyte *)input);
    if ((*env)->ExceptionCheck(env))
        return NULL;
    if (lz4kd_decode(input, output, len, PAGE_BYTES) != PAGE_BYTES)
        return NULL;
    return byte_array(env, output, PAGE_BYTES);
}
