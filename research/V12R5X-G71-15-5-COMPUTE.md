# V12R5X: 15 GPU graphics shaders + 5 GPU compute shaders

Target: Exynos 8895 / Mali-G71 MP20 / Samsung Galaxy S8+ G955F.

**Scope:** Keep all 15 assigned graphics shaders available on normal JS0/JS1,
and reserve 5 other shader cores for compute JS2. This is GPU compute
partitioning, **not** a new neural processing unit and **not** an MGLRU
hardware offload.

Changes relative to V12R5V:
- Check exactly 20 physically present shaders and exactly 2 coherent groups.
- Choose all five compute shaders from the existing second coherent group.
- NEVER borrow shaders from first coherent group.
- Verify 15+5 masks are non-overlapping and together cover all present shaders.
- If the hardware cannot satisfy these invariants, return to stock FULL
  20-core masks for JS0, JS1 and JS2, with a visible kernel log.
- Preserve the Exynos 8895 GPU interactive DVFS and its original 546 MHz
  `gpu_max_clock` limit and GPU thermal control in DTS. No frequency capping,
  overclocking or thermal bypass added. Under load all 15 assigned graphic
  shaders remain addressable, but GPU clocks may scale safely by design.
- VPU vision hardware driver remains unchanged, and is not inserted into the
  synchronous page reclaim / page-table walking path.
- Preserve zRAM, PSI/LMKD, existing MGLRU code and **MGLRU default OFF**.

Caveats:
- JS2 only gets explicit ONLY_COMPUTE work targeted to coherent group 1.
- Shader partition cannot manufacture a standalone NPU or solve a kernel
  deadlock. Linux page reclaim holds CPU-side page structures and locks.
- Compilation and a valid boot image do not establish real-hardware boot
  safety. If an S8+ fails boot BEFORE manually enabling MGLRU, that is a
  boot/driver/integration problem, not evidence of active MGLRU reclaim.
- Keep the existing V12R5T known-good Boot image as recovery.
