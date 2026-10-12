# V12R5X - CPU V12R5T unchanged / GPU 15 graphics + 5 compute / VPU independent

## What is implemented

- Base is V12R5W, which inherits the V12R5T CPU frequency, voltage
  and thermal policy, verified by identical file hashes.
- The Exynos8895 Mali-G71 r19p0 backend has validated 15 graphics vs 5
  compute shader masks. This is *job slot scheduling*, not a new NPU.
- Refuse splitting if GPU has fewer/more than 20 available shader cores,
  if there are not exactly two coherency groups, or if coherency group 1
  cannot provide all five compute shaders. Fall back to stock all-core mask.
- JS2 is available only for an ONLY_COMPUTE device_nr=1 atom on a two-group
  GPU, as defined by `kbase_js_get_slot()`. Apps must separately submit
  suitable jobs; ordinary Android inference apps will not automatically use JS2.
- Samsung VPU remains compiled, but its imaging driver is **not** merged
  with Mali GPU hardware. A shared higher-level compute coordinator needs
  a userspace implementation and compatible kernel/vendor interfaces.
- MGLRU reclaim runs on the CPU only, with MGLRU default OFF. Neither
  GPU nor VPU can own CPU page tables or zone spinlocks. Converting pressure
  metrics to a recommendation off CPU would not move actual page reclaim.

## Explicit blockers before claiming finished AI / NPU / MGLRU offload

1. Verify shader coherency group topology on real G955F. Firmware may
   reject masks; an unsupported layout deliberately falls back.
2. Implement a supported GPU compute application or inference runtime
   that demonstrably submits ONLY_COMPUTE device_nr=1 jobs to JS2.
3. Add independent VPU workloads through Samsung's VPU interface.
4. Validate both concurrently with thermal/performance instrumentation.
5. Fix MGLRU's actual kernel-side no-progress/die cause using live
   pstore, VM/PSI counters. Do not enable MGLRU during boot diagnostics.

CI compile, boot header and Android ramdisk integrity do not prove steps 1-5.
Do not advertise this as NPU hardware or flash-ready without testing.
