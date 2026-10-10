#!/usr/bin/env python3
"""Fail-closed uniLoader P8 debug instrumentation for known pinned source.

This does NOT change memory addresses, PMIC, Linux kernel or Android init.
Only prints stage markers and compares copied payload bytes.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: p8-instrument-uniloader-handoff.py /path/to/uniLoader")
p=Path(sys.argv[1])/"arch/aarch64/load-kernel.c"
if not p.is_file():
    raise SystemExit("Expected pinned uniLoader arch/aarch64/load-kernel.c")
s=p.read_text()
old='''#include <main/boot.h>
#include <string.h>

void arch_load_kernel(void* kernel, void* dt, void* ramdisk)
{
\tmemcpy((void*)CONFIG_PAYLOAD_ENTRY, kernel, (unsigned long) &kernel_size);
#ifndef CONFIG_RAMDISK_NO_COPY
\t__optimized_memcpy((void*)CONFIG_RAMDISK_ENTRY, ramdisk, (unsigned long) &ramdisk_size);
#endif
\tload_kernel_and_jump(dt, 0, 0, 0, (void*)CONFIG_PAYLOAD_ENTRY);
}
'''
assert s.count(old)==1, "Pinned uniLoader boot path unexpectedly changed; STOP"
new='''#include <main/boot.h>
#include <string.h>
#include <lib/debug.h>

/* ALICE_P8 instrumented diagnostics: no PMIC or external hardware writes.
 * stage strings rendered by already initialized simplefb; visibility is NOT
 * sufficient to establish that Linux 5.10 actually executed.
 */
void arch_load_kernel(void* kernel, void* dt, void* ramdisk)
{
\tunsigned long n = (unsigned long)&kernel_size;
\tprintk(KERN_NOTICE, "ALICE_P8_COPY_KERNEL_BEGIN\\\\n");
\tif (n < 64 || n > 0x8000000) {
\t\tprintk(KERN_EMERG, "ALICE_P8_INVALID_KERNEL_SIZE\\\\n");
\t\treturn;
\t}
\tmemcpy((void*)CONFIG_PAYLOAD_ENTRY, kernel, n);
\tprintk(KERN_NOTICE, "ALICE_P8_COPY_KERNEL_DONE\\\\n");
\tif (memcmp((void*)CONFIG_PAYLOAD_ENTRY, kernel, 64) ||
\t    memcmp((char*)CONFIG_PAYLOAD_ENTRY + n - 64,
\t           (char*)kernel + n - 64, 64)) {
\t\tprintk(KERN_EMERG, "ALICE_P8_KERNEL_COPY_MISMATCH\\\\n");
\t\treturn;
\t}
\tprintk(KERN_NOTICE, "ALICE_P8_KERNEL_COPY_VERIFIED\\\\n");
#ifndef CONFIG_RAMDISK_NO_COPY
\tunsigned long rn = (unsigned long)&ramdisk_size;
\tif (rn < 64 || rn > 0x800000) {
\t\tprintk(KERN_EMERG, "ALICE_P8_INVALID_RAMDISK_SIZE\\\\n");
\t\treturn;
\t}
\tprintk(KERN_NOTICE, "ALICE_P8_COPY_RAMDISK_BEGIN\\\\n");
\t__optimized_memcpy((void*)CONFIG_RAMDISK_ENTRY, ramdisk, rn);
\tprintk(KERN_NOTICE, "ALICE_P8_COPY_RAMDISK_DONE\\\\n");
\tif (memcmp((void*)CONFIG_RAMDISK_ENTRY, ramdisk, 64) ||
\t    memcmp((char*)CONFIG_RAMDISK_ENTRY + rn - 64,
\t           (char*)ramdisk + rn - 64, 64)) {
\t\tprintk(KERN_EMERG, "ALICE_P8_RAMDISK_COPY_MISMATCH\\\\n");
\t\treturn;
\t}
\tprintk(KERN_NOTICE, "ALICE_P8_RAMDISK_COPY_VERIFIED\\\\n");
#endif
\tprintk(KERN_NOTICE, "ALICE_P8_BEFORE_ARM64_BRANCH\\\\n");
\t/* No changes to exception level, MMU, cache maintenance or entry point.
\t * If copy succeeds and kernel stays silent, these are the next suspects.
\t */
\tload_kernel_and_jump(dt, 0, 0, 0, (void*)CONFIG_PAYLOAD_ENTRY);
}
'''
# Strings are C escaped newlines, not raw literal newline characters.
new=new.replace(chr(92)*2 + "n", chr(92) + "n")
assert 'ALICE_P8_BEFORE_ARM64_BRANCH' in new
p.write_text(s.replace(old,new))
print("P8 instrumented before/after kernel & ramdisk copy and ARM64 branch")
