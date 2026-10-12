# ALICE V12R69 – SystemUI / MGLRU / LMKD evidence-driven stabilization

Base: `agent/v12r68-energy-step-governor-research`.

## Confirmed from V12R68 device log, 2026-10-12

* Kernel V12R68 boots, Energy Step active on policy0 and policy4.
* In the captured lag episode, MGLRU sysfs `enabled=0`: the lag must not be attributed exclusively to active MGLRU.
* Android SystemUI Choreographer logged prolonged skipped frames.
* LMKD repeatedly logged `Reclaim '…' … reason: low watermark is breached and swap is low` with free swap about 2.56 GiB versus threshold ~2.617 GiB. This is **not proof** that LMKD killed Launcher.
* One UI Launcher restarted in earlier live snapshots, but precise terminating actor remains unknown.

## Required changes, gated by evidence

1. Identify the userspace source of `lru_gen/enabled=0` instead of indefinitely blocking all runtime OFF writes. Current boot guard applies to only one init child shell write in the first 60 seconds.
2. Capture synchronized PSI, workingset refault, reclaim and UI-thread logs around **the same** Home/notification gesture. Cumulative refault without elapsed time is not diagnostic.
3. Inspect runtime vendor `lmkd` config and low-swap watermark source **before changing** thresholds. Do not disable lmkd or Chimera; no permanent process pinning.
4. Compare MGLRU OFF/ON under the same governor, then compare energy_step/schedutil while holding MGLRU constant.
5. Verify thermal, suspend/resume, app switching and boot stability before repacking boot.

## Collection on device
`su -c 'sh /data/local/tmp/alice-v12r69-snapshot.sh'`

This commit introduces a non-destructive diagnostic tool, **not** a functional kernel/LMKD patch. Boot flash-readiness remains unverified.
