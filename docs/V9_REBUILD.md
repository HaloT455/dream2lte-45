# ALice V9 rebuild policy

V9 starts from the known-good V6 commit `a15290cd8ce62e309d6c071df4cebd9177d9e4a4`.

## Non-negotiable baseline

- Keep the V6 Samsung 4.4 boot, watchdog suspend, EAS/WALT schedutil and
  KernelSU manual-hook paths unchanged until a baseline build passes.
- Keep Cortex-A53 2002 MHz and Mongoose M2 2704 MHz source ceilings.
- Keep the 65 C thermal policy and stock ASV/ABB/voltage logic.
- Build separate SELinux Enforcing and Permissive packages.
- Preserve the installed ROM ramdisk by flashing only Image and DTB through
  AnyKernel3.

## Port order

1. Build the exact V6 runtime as a V9 baseline.
2. Add verified non-MM changes (dual-SIM declaration and Mali 455 MHz cap).
3. Add memory changes independently; never import the V8 MM commit chain as a
   bulk merge.
4. Keep a no-MGLRU V9 package as the recovery/control build when testing MGLRU.
5. Require compile, DTB decompile and package-integrity checks at every stage.
