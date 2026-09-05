# MGLRU eviction: invalid Linux 4.4 output pointers

## Confirmed source defect

V8 through kernel build `c02ad62b` calls `shrink_page_list()` from
`evict_pages()` with five NULL output pointers. The Linux 4.4 function
unconditionally accumulates dirty, unqueued-dirty, congested, writeback and
immediate counts through these pointers before returning.

Once MGLRU isolates a batch and invokes this function, the output stores
access address zero. This is a kernel crash defect even when no pages were
successfully freed. Compiler success and boot-image structure checks do not
validate this pointer contract. The legacy V6 caller supplies actual local
storage; it does not execute this MGLRU path.

## Fix and regression check

Pass five separate initialized `unsigned long` counters from `evict_pages()`.
Initialization matters because the old API uses `+=`, rather than assignment.
The counters are currently unused by the MGLRU caller, but remain mandatory
arguments to the 4.4 callee. Keep the existing V6 baseline, MGLRU enabled,
SimpleLMK and SELinux variants.

`scripts/test_mglru_reclaim_args.py` extracts the actual caller's declarations
and invocation and the callee's output writes. A small host harness exercises
that boundary under UBSan. The `c02ad62b` source reproduces a NULL dereference;
the fixed source passes and verifies all five accumulated values. This check
does not simulate the complete reclaim algorithm or hardware execution.
CI runs it before the full kernel build.

## Device evidence and remaining verification

The user reports that the display appears for approximately 2-3 seconds
before the device crashes. The supplied Android log spans
17:13:14.110-17:13:15.312 (1.202 seconds), contains boot completion at
17:13:14.310 and a restarted lmkd reconnecting at 17:13:14.230, but no kernel
panic/stack or kernel version. BootReceiver reports `N|RP`, `CAUSE: reboot`
and an empty stack; that does not identify the faulting kernel instruction.

The source defect is confirmed and fits a crash when boot activity first
triggers MGLRU eviction. Matching it to this particular phone reset still
requires a pstore/last-kmsg stack or successful hardware verification of the
fixed build. Do not present the short logcat alone as proof of that match.
