# ALICE V12R64 — Resource Intelligence for Exynos 8895

## What is actually implemented
- Android userspace foreground controller, opt-in, samples **/proc/pressure/memory**,
  MemAvailable, SwapFree/Total, workingset_refault and current ALICE kernel VM
  state. Scores pressure into balanced/stability tiers, with two-sample
  confirmation and a 180-second cooldown before changing modes.
- When explicitly started, requests V12R61 kernel mode=4, enables only the
  preexisting bounded vm.swappiness policy, then adjusts mode=0 or mode=4
  according to measured pressure. Stop restores original swappiness.
- Qwen3-0.6B (real pretrained GGUF stored under /data) can analyze telemetry
  and make suggestions. No LLM-generated shell command ever runs automatically.
- Existing V12R63 process supervisor only alters nice of verified cached
  third-party apps, protecting foreground/system processes.

## MGLRU
- Exynos 8895 does NOT have an NPU able to manipulate CPU Linux page tables.
- Kernel V12R61 includes CONFIG_LRU_GEN but has it **OFF by default**.
- Only after double warning & user confirmation: a root helper attempts a
  12-second MGLRU test using /sys/kernel/mm/lru_gen/enabled with initial
  value 0 and MemAvailable >= 600000 kB.
- Trap restores OFF on normal completion/signals. **A kernel deadlock may
  prevent both the trap and rollback from running.** Do not do this before
  backing up Boot and user data. Not triggered by automatic service.

## LMKD
- Android lowmemorykiller daemon remains authoritative for reclaim-triggered
  cached-app killings. ALICE reads lmkd service status and ro.lmk.* and
  persist.device_config.lmkd_native.* properties.
- An optional **20-second** experiment sets
  persist.device_config.lmkd_native.thrashing_limit=60 and restores its
  previously configured value. Only allowed if init.svc.lmkd=running and
  the real device's lmkd.rc contains both a reinit trigger and property
  trigger for thrashing_limit.
- If ROM doesn't support dynamic property reinitialization, ALICE refuses
  to change LMKD. It does NOT blindly restart lmkd, turn it off or edit
  oom_score_adj, thresholds, minfree or protected apps.
- Property is persistent. Interruption, kernel hang or power loss during
  trial can prevent rollback. The app has a manual recovery command, but
  **no reboot-safe watchdog guarantee**.

## What is *not* implemented
- No automatic MGLRU ON, no GPU/VPU memory reclaim, and no modifications to
  CPU frequencies, thermal or voltage. GPU split 15/5 in V12R61 is a GPU job
  slot configuration only, not a real neural accelerator.
- Resource loop uses deterministic safety rules/hysteresis. Qwen inference
  is on-demand, not a 45-second kernel scheduling oracle.
- No user-device verification yet on Galaxy S8+ One UI 8 Android 16.
- No proof that vendor Samsung LMKD supports runtime tuning until the ROM
  is checked by the controller on that specific phone.

## Files
- alice/android-app/app/src/main/java/com/halot455/alice/AliceResourceEngine.java
- alice/android-app/app/src/main/java/com/halot455/alice/AliceResourceService.java
- alice/android-app/app/src/main/assets/alice_memory.sh
- alice/android-app/app/src/main/java/com/halot455/alice/MainActivity.java

References:
- Android AOSP LMKD official memory-performance documentation.
- AOSP lmkd property override uses persist.device_config.lmkd_native.*
  and init.rc triggers for reinit; these are NOT guaranteed in Samsung ROMs.
