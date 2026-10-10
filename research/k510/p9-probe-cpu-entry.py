#!/usr/bin/env python3
"""P9: non-mutating architectural state inspection before ARM64 Linux entry.

Applied AFTER P8 stage instrumentation in pinned uniLoader source.
No MMU/cache/interrupt modifications, no speculative MMIO writes.
"""
from pathlib import Path
import sys
if len(sys.argv) != 2:
    raise SystemExit("usage: p9-probe-cpu-entry.py /path/to/uniLoader")
p=Path(sys.argv[1])/"arch/aarch64/load-kernel.c"
s=p.read_text()
anchor='printk(KERN_NOTICE, "ALICE_P8_BEFORE_ARM64_BRANCH\\n");'
if s.count(anchor) != 1:
    raise SystemExit("FAIL CLOSED: P8 pre-branch marker missing or altered")
probe=r"""
	/* P9: safe observational read-only ARM64 state probe.
	 * Never modify SCTLR, DAIF, cache or exception level in this build.
	 */
	{
		unsigned long elraw, daif, sctlr = 0;
		unsigned int el;
		__asm__ volatile("mrs %0, CurrentEL" : "=r"(elraw));
		__asm__ volatile("mrs %0, DAIF" : "=r"(daif));
		el = (unsigned int)(elraw >> 2);
		printk(KERN_NOTICE, "ALICE_P9_ENTRY_EL_%u\n", el);
		if (el == 1) {
			__asm__ volatile("mrs %0, SCTLR_EL1" : "=r"(sctlr));
		} else if (el == 2) {
			__asm__ volatile("mrs %0, SCTLR_EL2" : "=r"(sctlr));
		} else {
			printk(KERN_EMERG, "ALICE_P9_EL_UNEXPECTED\n");
			return;
		}
		printk(KERN_NOTICE, "ALICE_P9_MMU_%u_DCACHE_%u_ICACHE_%u\n",
		       (unsigned)(sctlr & 1u),
		       (unsigned)((sctlr >> 2) & 1u),
		       (unsigned)((sctlr >> 12) & 1u));
		printk(KERN_NOTICE, "ALICE_P9_DAIF_D%u_A%u_I%u_F%u\n",
		       (unsigned)((daif >> 9) & 1u),
		       (unsigned)((daif >> 8) & 1u),
		       (unsigned)((daif >> 7) & 1u),
		       (unsigned)((daif >> 6) & 1u));
		printk(KERN_NOTICE, "ALICE_P9_DTB_ALIGN8_%u\n",
		       (unsigned)!(((unsigned long)dt) & 7u));
		printk(KERN_NOTICE, "ALICE_P9_STATE_READ_DONE\n");
	}
"""
# Insert on next line BEFORE original P8 pre-branch marker.
# Match C source exactly including the literal \n escape, do not create
# a raw newline inside quoted C strings.
probe = probe.replace(chr(92)*2+"n", chr(92)+"n")
s=s.replace(anchor,probe+"\t"+anchor)
p.write_text(s)
print("P9 state instrumentation inserted before P8 ARM64 branch; observation only")
