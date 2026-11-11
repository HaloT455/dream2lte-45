obj-$(CONFIG_ZSTD_COMPRESS) += zstd_compress.o
obj-$(CONFIG_ZSTD_DECOMPRESS) += zstd_decompress.o

ccflags-y += -O3

zstd_compress-y := fse_compress.o huf_compress.o compress.o \
		   entropy_common.o fse_decompress.o zstd_common.o
zstd_decompress-y := huf_decompress.o decompress.o

# Link common objects once when both libraries are built into vmlinux.
ifneq ($(CONFIG_ZSTD_COMPRESS)$(CONFIG_ZSTD_DECOMPRESS),yy)
zstd_decompress-y += entropy_common.o fse_decompress.o zstd_common.o
endif
