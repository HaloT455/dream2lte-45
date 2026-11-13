#!/usr/bin/env python3
"""Exercise the kernel LZ4KD codec and crypto adapter with 4 KiB pages."""

import ctypes
import os
from pathlib import Path
import random
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PAGE = 4096


def build_codec(work, output):
    stubs = work / "linux"
    stubs.mkdir()
    (stubs / "lz4kd.h").symlink_to(ROOT / "include/linux/lz4kd.h")
    (work / "lz4kd.h").symlink_to(stubs / "lz4kd.h")
    (stubs / "crypto.h").write_text(r"""
#include <errno.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;
struct crypto_tfm { void *workspace; };
#define crypto_tfm_ctx(tfm) (&(tfm)->workspace)
#define CRYPTO_ALG_TYPE_COMPRESS 2
#define THIS_MODULE 0
struct crypto_alg {
    const char *cra_name, *cra_driver_name;
    int cra_flags, cra_ctxsize, cra_module;
    int (*cra_init)(struct crypto_tfm *);
    void (*cra_exit)(struct crypto_tfm *);
    struct { struct {
        int (*coa_compress)(struct crypto_tfm *, const u8 *, unsigned, u8 *, unsigned *);
        int (*coa_decompress)(struct crypto_tfm *, const u8 *, unsigned, u8 *, unsigned *);
    } compress; } cra_u;
};
#define crypto_register_alg(alg) (0)
#define crypto_unregister_alg(alg) ((void)(alg))
""")
    (stubs / "init.h").write_text("#define __init\n#define __exit\n")
    (stubs / "mm.h").write_text("#define PAGE_SIZE 4096u\n")
    (stubs / "module.h").write_text(r"""
#define module_init(x)
#define module_exit(x)
#define MODULE_LICENSE(x)
#define MODULE_DESCRIPTION(x)
#define MODULE_ALIAS_CRYPTO(x)
""")
    (stubs / "vmalloc.h").write_text(r"""
#include <stdlib.h>
#define vmalloc malloc
#define vfree free
""")
    wrapper = work / "adapter.c"
    wrapper.write_text(r"""
#include "crypto/lz4kd.c"
static struct crypto_tfm context;

int probe_init(void) { return lz4kd_init(&context); }
void probe_exit(void) { lz4kd_exit(&context); }

int probe_compress(const u8 *in, unsigned size, u8 *out, unsigned cap)
{
    int result = lz4kd_compress(&context, in, size, out, &cap);
    return result ? result : (int)cap;
}

int probe_decompress(const u8 *in, unsigned size, u8 *out, unsigned cap)
{
    int result = lz4kd_decompress(&context, in, size, out, &cap);
    return result ? result : (int)cap;
}
""")
    subprocess.run([
        os.environ.get("CC", "cc"), "-shared", "-fPIC", "-O3", "-I", work,
        "-I", ROOT, wrapper,
        ROOT / "lib/lz4kd/lz4kd_encode.c", ROOT / "lib/lz4kd/lz4kd_decode.c",
        "-o", output,
    ], check=True)


def check_pages(codec):
    args = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    compress, decompress = codec.probe_compress, codec.probe_decompress
    compress.argtypes = decompress.argtypes = args
    rng = random.Random(8895)
    noise = rng.randbytes(PAGE)
    pages = [noise, bytes(PAGE), b"1234" * 1024]
    for length in (4, 63, 64, 67, 255, 4095):
        for offset in (0, (PAGE - length) // 2, PAGE - length):
            pages.append(noise[:offset] + b"\xff" * length + noise[offset + length:])
    for alphabet in (2, 8, 16, 64, 256):
        for _ in range(70):
            pages.append(bytes(rng.randrange(alphabet) for _ in range(PAGE)))
    for _ in range(320):
        pages.append(b"".join(
            bytes([rng.randrange(256)]) * 64 if rng.randrange(3) else rng.randbytes(64)
            for _ in range(PAGE // 64)
        ))

    packed = ctypes.create_string_buffer(PAGE * 2 + 16)
    decoded = ctypes.create_string_buffer(PAGE + 16)
    compressed_pages = raw_pages = 0
    for index, page in enumerate(pages):
        ctypes.memset(packed, 0xA5, len(packed))
        ctypes.memset(decoded, 0x5A, len(decoded))
        size = compress(page, PAGE, packed, 2 * PAGE)
        assert 0 < size <= PAGE, (index, size)
        assert packed.raw[-16:] == b"\xa5" * 16
        if size == PAGE:
            assert packed.raw[:PAGE] == page
            raw_pages += 1
        else:
            compressed_pages += 1
        assert decompress(packed, size, decoded, PAGE) == PAGE, (index, size)
        assert decoded.raw[:PAGE] == page, index
        assert decoded.raw[-16:] == b"\x5a" * 16
    assert compressed_pages > 100 and raw_pages > 50
    assert compress(noise, PAGE, packed, PAGE) < 0
    assert decompress(packed, PAGE, decoded, PAGE - 1) < 0
    assert decompress(packed, 2 * PAGE, decoded, PAGE) < 0
    assert decompress(b"\x00" * 4, 4, decoded, PAGE) < 0
    print(f"LZ4KD 4 KiB round-trip: {compressed_pages} compressed, {raw_pages} raw")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        output = work / "lz4kd-test.so"
        build_codec(work, output)
        codec = ctypes.CDLL(str(output))
        codec.probe_exit.restype = None
        assert codec.probe_init() == 0
        try:
            check_pages(codec)
        finally:
            codec.probe_exit()


if __name__ == "__main__":
    main()
