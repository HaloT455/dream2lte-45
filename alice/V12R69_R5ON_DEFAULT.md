# V12R69 R5-ON: MGLRU enabled at boot

The user explicitly requests MGLRU enabled by default. Relative to R5 commit
e1e0336fab9a472d0f742d751b458c979ba6b3ae, this enables CONFIG_LRU_GEN_ENABLED,
updates the release banner/CI assertions, and updates the existing checks.
The MGLRU static key and per-zone generation state initialize enabled.
Existing One UI early-init compatibility is compiled; ordinary runtime OFF
remains available. No resident app or service.d loop forces MGLRU back ON.

EnergyStep's hardware-step selection, worker locking, deadline-load repair,
rate limits and driver policy constraints remain unchanged. The app keeps only
LRU controls/logs. GPU compute partition remains disabled, the ALICE bridge is
read-only, and no Qwen/process/VM AI service is restored.

CI builds the enforcing ARM64 kernel. Boot must be repacked locally from the
exact R66 base, preserving ramdisk/DTB/header addresses/footer. Private boot
parts are excluded from the public source repository.

Host checks and CI do not prove physical two-app reclaim or thermal stability.
The previously reported freeze/heat remain unverified; boot ON is a requested
configuration change, not a demonstrated fix for those runtime failures.
