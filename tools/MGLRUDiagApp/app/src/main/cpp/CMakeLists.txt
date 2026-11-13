cmake_minimum_required(VERSION 3.22)
project(halo_lz4kd C)

set(kernel "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../..")
configure_file("${kernel}/include/linux/lz4kd.h" lz4kd.h COPYONLY)
add_library(halo_lz4kd SHARED
    halo_lz4kd_jni.c
    "${kernel}/lib/lz4kd/lz4kd_encode.c"
    "${kernel}/lib/lz4kd/lz4kd_decode.c"
)
target_include_directories(halo_lz4kd PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
target_compile_options(halo_lz4kd PRIVATE -O3)
