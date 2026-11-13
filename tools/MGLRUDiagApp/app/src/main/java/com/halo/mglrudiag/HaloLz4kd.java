package com.halo.mglrudiag;

final class HaloLz4kd {
    static {
        System.loadLibrary("halo_lz4kd");
    }

    private HaloLz4kd() {}

    static native byte[] compress(byte[] page);
    static native byte[] decompress(byte[] block);
}
