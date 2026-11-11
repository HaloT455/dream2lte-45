#!/usr/bin/env python3
"""Run the Android compute shader with headless Mesa and decode each frame."""

import ctypes as ct
from pathlib import Path
import random
import struct

PAGE_BYTES = 4096
SHADER = (Path(__file__).resolve().parents[1] /
          "tools/MGLRUDiagApp/app/src/main/assets/zstd_pages.comp")

EGL_NONE = 0x3038
GL_SHADER_STORAGE_BUFFER = 0x90D2
GL_BUFFER_UPDATE_BARRIER_BIT = 0x0200
GL_MAP_READ_BIT = 1


def function(lib, name, result, *params):
    fn = getattr(lib, name)
    fn.restype = result
    fn.argtypes = params
    return fn


def make_current():
    egl = ct.CDLL("libEGL.so.1")
    ptr, i, ip = ct.c_void_p, ct.c_int, ct.POINTER(ct.c_int)
    display = function(egl, "eglGetDisplay", ptr, ptr)(None)
    assert function(egl, "eglInitialize", i, ptr, ip, ip)(display, None, None)
    assert function(egl, "eglBindAPI", i, ct.c_uint)(0x30A0)  # EGL_OPENGL_ES_API
    config_attrs = (i * 5)(0x3033, 1, 0x3040, 0x40, EGL_NONE)
    config, count = ptr(), i()
    choose = function(egl, "eglChooseConfig", i, ptr, ip, ct.POINTER(ptr), i, ip)
    assert choose(display, config_attrs, ct.byref(config), 1, ct.byref(count)) and count.value
    context = function(egl, "eglCreateContext", ptr, ptr, ptr, ptr, ip)(
        display, config, None, (i * 3)(0x3098, 3, EGL_NONE))
    surface = function(egl, "eglCreatePbufferSurface", ptr, ptr, ptr, ip)(
        display, config, (i * 5)(0x3057, 1, 0x3056, 1, EGL_NONE))
    assert context and surface
    assert function(egl, "eglMakeCurrent", i, ptr, ptr, ptr, ptr)(
        display, surface, surface, context)
    return function(egl, "eglGetProcAddress", ptr, ct.c_char_p)


def compute(pages):
    proc = make_current()
    uint, i, ip, ptr = ct.c_uint, ct.c_int, ct.POINTER(ct.c_int), ct.c_void_p

    def gl(name, result, *params):
        address = proc(name.encode())
        assert address, name
        return ct.CFUNCTYPE(result, *params)(address)

    def check_object(obj, status, query, info):
        passed = i()
        gl(query, None, uint, uint, ip)(obj, status, ct.byref(passed))
        if not passed.value:
            log = ct.create_string_buffer(4096)
            gl(info, None, uint, i, ip, ptr)(obj, len(log), None, log)
            raise AssertionError(log.value.decode())

    print(gl("glGetString", ct.c_char_p, uint)(0x1F01).decode())  # GL_RENDERER
    shader = gl("glCreateShader", uint, uint)(0x91B9)
    src = ct.c_char_p(SHADER.read_bytes())
    gl("glShaderSource", None, uint, i, ct.POINTER(ct.c_char_p), ip)(
        shader, 1, ct.byref(src), None)
    gl("glCompileShader", None, uint)(shader)
    check_object(shader, 0x8B81, "glGetShaderiv", "glGetShaderInfoLog")
    program = gl("glCreateProgram", uint)()
    gl("glAttachShader", None, uint, uint)(program, shader)
    gl("glLinkProgram", None, uint)(program)
    check_object(program, 0x8B82, "glGetProgramiv", "glGetProgramInfoLog")
    gl("glUseProgram", None, uint)(program)

    buffers = (uint * 3)()
    gl("glGenBuffers", None, i, ct.POINTER(uint))(3, buffers)
    bind = gl("glBindBuffer", None, uint, uint)
    total = len(pages) * PAGE_BYTES
    sizes = (total, total, len(pages) * 4)
    data = ct.create_string_buffer(b"".join(pages))
    for index, (buffer, size) in enumerate(zip(buffers, sizes)):
        bind(GL_SHADER_STORAGE_BUFFER, buffer)
        gl("glBufferData", None, uint, ct.c_ssize_t, ptr, uint)(
            GL_SHADER_STORAGE_BUFFER, size, data if index == 0 else None, 0x88E8)
        gl("glBindBufferBase", None, uint, uint, uint)(GL_SHADER_STORAGE_BUFFER, index, buffer)

    gl("glDispatchCompute", None, uint, uint, uint)(len(pages), 1, 1)
    gl("glMemoryBarrier", None, uint)(GL_BUFFER_UPDATE_BARRIER_BIT)
    gl("glFinish", None)()
    assert gl("glGetError", uint)() == 0

    def read_buffer(index):
        bind(GL_SHADER_STORAGE_BUFFER, buffers[index])
        size = sizes[index]
        address = gl("glMapBufferRange", ptr, uint, ct.c_ssize_t, ct.c_ssize_t, uint)(
            GL_SHADER_STORAGE_BUFFER, 0, size, GL_MAP_READ_BIT)
        assert address
        data = ct.string_at(address, size)
        assert gl("glUnmapBuffer", ct.c_ubyte, uint)(GL_SHADER_STORAGE_BUFFER)
        return data

    return struct.unpack("<" + "I" * len(pages), read_buffer(2)), read_buffer(1)


def main():
    rng = random.Random(8895)
    noisy = rng.randbytes(PAGE_BYTES)
    pages = [noisy, bytes(PAGE_BYTES), b"\xff" * PAGE_BYTES,
             b"\xa5" * 64 + noisy[64:], noisy[:-64] + b"\x5a" * 64,
             b"ABCD" * (PAGE_BYTES // 4)]
    for rate in range(1, 8):
        for _ in range(12):
            tiles = [bytes([rng.randrange(256)]) * 64 if rng.randrange(8) < rate
                     else rng.randbytes(64) for _ in range(64)]
            pages.append(b"".join(tiles))
    lengths, output = compute(pages)

    zstd = ct.CDLL("libzstd.so.1")
    size, ptr = ct.c_size_t, ct.c_void_p
    decompress = function(zstd, "ZSTD_decompress", size, ptr, size, ptr, size)
    dest = ct.create_string_buffer(PAGE_BYTES)
    for index, (page, length) in enumerate(zip(pages, lengths)):
        has_rle = any(page[i:i + 64] == bytes([page[i]]) * 64
                      for i in range(0, PAGE_BYTES, 64))
        assert (0 < length < PAGE_BYTES) if has_rle else length == 0, (index, length)
        if length:
            start = index * PAGE_BYTES
            frame = output[start:start + length]
            assert decompress(dest, PAGE_BYTES, frame, length) == PAGE_BYTES, index
            assert dest.raw == page, index
    print(f"ZSTD round-trip: {sum(bool(n) for n in lengths)} GPU frames, "
          f"{sum(n == 0 for n in lengths)} CPU fallbacks")


if __name__ == "__main__":
    main()
