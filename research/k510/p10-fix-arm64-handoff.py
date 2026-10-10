#!/usr/bin/env python3
"""P10: ARM64 Linux entry contract repairs for known P9 uniLoader.

Adds architected data cache CLEAN to Point of Coherency for the copied Linux
Image, initramfs, and patched FDT; invalidate kernel instruction cache range;
set PSTATE.DAIF all masked. Does not change MMU, exception level, MMIO/PMIC,
memory address or Linux kernel/vendor drivers. Experimental on SM-G955F.
"""
from pathlib import Path
import sys
if len(sys.argv) != 2:
    raise SystemExit("usage: p10-fix-arm64-handoff.py /path/to/uniLoader")
p = Path(sys.argv[1]) / "arch/aarch64/load-kernel.c"
s = p.read_text()
for required in ("ALICE_P8_BEFORE_ARM64_BRANCH", "ALICE_P9_STATE_READ_DONE",
                 "ALICE_P8_KERNEL_COPY_VERIFIED", "ALICE_P8_RAMDISK_COPY_VERIFIED"):
    if required not in s:
        raise SystemExit("Expected P8/P9 instrumentation absent: " + required)
anchor = "\tload_kernel_and_jump(dt, 0, 0, 0, (void*)CONFIG_PAYLOAD_ENTRY);"
if s.count(anchor) != 1:
    raise SystemExit("Unexpected ARM64 kernel handoff call; stop")
# Do not change source layout / load addresses in this patch.
funcs = r"""
/* P10: clean copied payloads to PoC; invalidate newly copied Image to PoU.
 * ctr_el0 has DminLine[19:16], IminLine[3:0] in log2(words/line).
 * These operations are architectural and may still fault on a platform with
 * an invalid mapping; the real-device result is NOT known.
 */
static int alice_p10_cache_range(void *base, unsigned long len, int is_image)
{
	unsigned long ctr, dline, iline, addr, end, start;
	if (!base || !len || len > 0x8000000ul)
		return -1;
	start = (unsigned long)base;
	if (start + len < start)
		return -1;
	end = start + len;
	__asm__ volatile("mrs %0, ctr_el0" : "=r"(ctr));
	dline = 4ul << ((ctr >> 16) & 15ul);
	iline = 4ul << (ctr & 15ul);
	if (dline < 16 || dline > 1024 || iline < 16 || iline > 1024)
		return -2;
	addr = start & ~(dline - 1ul);
	for (; addr < end; addr += dline)
		__asm__ volatile("dc cvac, %0" : : "r"(addr) : "memory");
	__asm__ volatile("dsb sy" : : : "memory");
	if (is_image) {
		addr = start & ~(iline - 1ul);
		for (; addr < end; addr += iline)
			__asm__ volatile("ic ivau, %0" : : "r"(addr) : "memory");
		__asm__ volatile("dsb sy\n\tisb" : : : "memory");
	}
	return 0;
}

static unsigned long alice_p10_fdt_len(void *dt)
{
	const unsigned char *d = (const unsigned char *)dt;
	unsigned long size;
	if (!d || ((unsigned long)d & 7ul))
		return 0;
	/* standard flattened device tree: BE magic 0xd00dfeed, totalsize */
	if (d[0] != 0xd0 || d[1] != 0x0d || d[2] != 0xfe || d[3] != 0xed)
		return 0;
	size = ((unsigned long)d[4] << 24) | ((unsigned long)d[5] << 16) |
	       ((unsigned long)d[6] << 8) | (unsigned long)d[7];
	return (size >= 40 && size <= 0x200000ul) ? size : 0;
}
"""
needle = "void arch_load_kernel(void* kernel, void* dt, void* ramdisk)"
if s.count(needle) != 1:
    raise SystemExit("Cannot locate uniLoader kernel transfer function")
s = s.replace(needle, funcs + "\n" + needle)
injection = r"""
	/* Mask D, A (SError), I and F before ARM64 Linux entry.
	 * P9 measured DAIF_D1_A0_I1_F1: A0 violated the Linux boot ABI.
	 */
	{
		unsigned long daif_after, dtb_len;
		__asm__ volatile("msr daifset, #0xf\n\tisb" : : : "memory");
		__asm__ volatile("mrs %0, daif" : "=r"(daif_after));
		if (((daif_after >> 6) & 15ul) != 15ul) {
			printk(KERN_EMERG, "ALICE_P10_DAIF_MASK_FAILED\n");
			return;
		}
		printk(KERN_NOTICE, "ALICE_P10_DAIF_ALL_MASKED\n");
		printk(KERN_NOTICE, "ALICE_P10_KERNEL_CLEAN_BEGIN\n");
		if (alice_p10_cache_range((void*)CONFIG_PAYLOAD_ENTRY, n, 1)) {
			printk(KERN_EMERG, "ALICE_P10_KERNEL_CACHE_ERROR\n");
			return;
		}
		printk(KERN_NOTICE, "ALICE_P10_KERNEL_CACHE_READY\n");
#ifndef CONFIG_RAMDISK_NO_COPY
		if (alice_p10_cache_range((void*)CONFIG_RAMDISK_ENTRY, rn, 0)) {
			printk(KERN_EMERG, "ALICE_P10_RAMDISK_CACHE_ERROR\n");
			return;
		}
		printk(KERN_NOTICE, "ALICE_P10_RAMDISK_CACHE_READY\n");
#endif
		dtb_len = alice_p10_fdt_len(dt);
		if (!dtb_len) {
			printk(KERN_EMERG, "ALICE_P10_INVALID_DTB\n");
			return;
		}
		if (alice_p10_cache_range(dt, dtb_len, 0)) {
			printk(KERN_EMERG, "ALICE_P10_DTB_CACHE_ERROR\n");
			return;
		}
		printk(KERN_NOTICE, "ALICE_P10_DTB_CACHE_READY\n");
		__asm__ volatile("dsb sy\n\tisb" : : : "memory");
		printk(KERN_NOTICE, "ALICE_P10_READY_TO_BRANCH\n");
	}
"""
s = s.replace(anchor, injection + "\t" + anchor)
p.write_text(s)
print("P10: DAIF mask + PoC Image/ramdisk/FDT clean + I-cache invalidate inserted")
