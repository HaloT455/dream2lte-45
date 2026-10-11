# ALICE V12R5W - boot isolation, NOT neural MGLRU offload

## Confirmed

- Exynos 8895 GPU: Mali G71 MP20. VPU supports vision algorithms; neither
  provides access to kernel task page tables or per-zone LRU list locks.
- V12R5V already compiles `CONFIG_MALI_HALO_NPU_PARTITION=y`. Its C code
  limits GPU job slots JS0/JS1 and JS2 to different shader masks; there is no
  kernel-to-GPU memory-reclaim transport. Calling this NPU is a misleading label.
- V12R5V kernel image sets `CONFIG_LRU_GEN=y` but default-enabled is OFF.
  Consequently a boot failure before manual MGLRU activation is not evidence
  that MGLRU was active when the boot failure occurred.
- The V12R5V boot image using V12R5T ramdisk and DTB has valid Android boot
  header SHA1 and identical ramdisk/DTB; this is not proof of bootability.

## One-variable isolation

- Base: `agent/v12r5v-mglru-lowram-reclaim-safety`
- Change: disable `CONFIG_MALI_HALO_NPU_PARTITION` only.
- Expected: Mali driver resumes stock GPU shader-present mask for all job slots.
- Unchanged: VPU driver; MGLRU code defaults OFF; zRAM; LMKD/PSI; other kernel
  subsystems and Android ramdisk.
- Do not enable MGLRU to test a boot failure; first confirm system is stable.

## Evidence needed before flash-ready

1. arm64 build and DTB validate with enforcing config.
2. Preserve known V12R5T ramdisk/DTB and verify all boot header fields + SHA1.
3. Confirm boot to Android and no GPU scheduler/softdog resets on real G955F.
4. Separately capture MGLRU enabled=0 and then opt-in after baseline stability.

This is an experimental **boot-isolation** build. It does not promise that a
reboot/reset caused by unverified GPU firmware, userspace vendor drivers, or
MGLRU reclaim has been repaired.
