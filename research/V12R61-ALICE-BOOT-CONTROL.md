# ALICE V12R61 – Boot image and Android controller
## Boot method
Built-in Linux kernel ALICE interface at `/sys/kernel/alice/`. Base ramdisk is
first-stage init with **no** init.rc services; do not inject a bogus service.
Keep the V12R5T first-stage ramdisk and original DTB identical. Replace only
the kernel and regenerate Android v0 boot header digest and kernel size.
No KernelSU module is necessary for reading ALICE kernel data.

## What is really handled in kernel
- VM scanned/reclaimed/no-progress/backoff counters when MGLRU performs work;
  memory and swap info; a lightweight, explicitly heuristic pressure rating
  derived from free pages and swap usage (not a trained ML model).
- Six user-selectable modes: balanced(0), performance(1), gaming(2),
  battery(3), stability(4), research(5). Modes are advisory unless policy is
  explicitly enabled by root via /sys/kernel/alice/policy_enabled.
- Opt-in VM setting adjusts ONLY vm.swappiness with conservative bounds.
  Other CPU/GPU frequency/voltage/thermal, LMKD, memory mappings, MGLRU switches,
  DTB, SELinux stay untouched. Policy defaults OFF with stability mode on boot.
- On disable, restores previous swappiness only if value has not been changed
  independently by another governor/ROM component.
- GPU 15+5 compute shader mask code is inherited from V12R5X and only engages
  on supported MP20 2-coherent-group topology. NO compute inference workload
  is submitted by the kernel bridge. VPU hardware driver stays independent.

## Android APK
- Reads version/safety/capabilities/assessment/reclaim/counters from boot kernel.
- Root-confirmed mode and opt-in swappiness policy controls.
- Presents accurate functionality matrix, offline rule responses, Android voice
  recognition where a provider is available, shareable diagnostic report.
- Online chat opens ChatGPT externally; there is no bundled local trained LLM.

## What is NOT implemented
- No real neural model or AI inference runtime on Galaxy S8+.
- No GPU + VPU unified runtime, VPU VS4L graph execution or MGLRU offload.
- No kernel optimization autotuner or device-tested thermal/game AI.
- No runtime/device boot certification; verify real G955F before production.

## Safety
Before boot flash, back up existing working Boot using TWRP. No MGLRU auto-enable.
Default mode stability(4), policy_enabled=0. If boot fails restore known-good boot.
Unlike KernelSU module, this built-in sysfs code does not persist mode across
reboots. Root authority is still required to modify these sysfs nodes.
