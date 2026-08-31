# MGLRU + SimpleLMK: dream2lte 4.4 port assessment

Status: **not integrated; no MGLRU boot has been built or validated.**
Date: 2026-08-31. Target kernel source is UI1-Trace commit
`b70a07db8b6b5d08beeb3c910a9c731b5cee941b`, identical in MM/SimpleLMK to
the tested UI1 base `887e9cc5e5678e6c8ee92bd9c8e0edecdaef4856`.
This document is a port checkpoint, not a performance change or a release.

## Evidence and candidate donor

The target has no `CONFIG_LRU_GEN`, generation lists, aging engine, or
MGLRU eviction/refault hooks. Adding config text or a sysfs switch alone
would not implement MGLRU.

The primary ChromeOS kernel repository was inspected:

- `chromeos-4.4` at `e2e07a89da87b5327149dad416d87c51c2a57b38` has no
  LRU_GEN Kconfig entry in the inspected MM Kconfig.
- `chromeos-4.14` at `43d4b1297e0ab9e971a2f6efaa76f5c9fa0f9f55` contains
  a page-based multigenerational LRU implementation, with aging, eviction,
  refault feedback, mm tracking, runtime enable and generation statistics.
- This is a real donor candidate, **not** a cleanly applicable 4.4 backport.
  Absence from these inspected sources is not proof that no 4.4 port exists
  anywhere. Mixed 4.4/4.19 release pages are not compatibility evidence.

Primary source:
https://chromium.googlesource.com/chromiumos/third_party/kernel/

Pinned donor files:
- https://chromium.googlesource.com/chromiumos/third_party/kernel/+/43d4b1297e0ab9e971a2f6efaa76f5c9fa0f9f55/mm/Kconfig
- https://chromium.googlesource.com/chromiumos/third_party/kernel/+/43d4b1297e0ab9e971a2f6efaa76f5c9fa0f9f55/mm/vmscan.c

## Concrete prerequisite gaps

| Area | Current dream2lte source | Donor requirement / work needed |
|---|---|---|
| LRU ownership/locks | `struct lruvec` points to a zone; `zone->lru_lock` | Donor uses `lruvec_pgdat()` and `pgdat->lru_lock`; reconcile locking and zone eligibility throughout reclaim, migration, swap and memcg, not with pointer casts/macros |
| Memory cgroups | `mem_cgroup_per_node` contains per-zone `zoneinfo[]`; `mem_cgroup_zone_lruvec()` | Donor generations are node/memcg based; port accounting and lifetime/iteration rules or implement and verify a genuine per-zone adaptation |
| Aging/rmap | No `struct page_vma_mapped_walk` in the inspected target headers/MM | Port required page-table/rmap walking APIs and ARM64 accessed-bit/TLB synchronization; preserve mmap/munmap/exit safety |
| Generation metadata | No generation bits/lists or mm tracking | Audit page flag space, initialization, fork/exit, memcg migration, LRU insertion/removal and runtime switching under concurrency |
| Reclaim pressure | Target `vmpressure(gfp, memcg, scanned, reclaimed, order)` and global notifier | Donor API/placement differs; preserve correct scanned/reclaimed deltas, low-scan critical notification and OOM fallback without duplicate notifications |

The older page-based donor reduces dependence on newer folio APIs, but does
not remove these prerequisites. A mechanical copy of `vmscan.c` would also
discard device-specific reclaim changes and is not an acceptable port.

## How MGLRU must cooperate with existing SimpleLMK

MGLRU chooses/ages pages and attempts reclaim; it is not an app killer.
SimpleLMK remains the severe-pressure process-reclamation path. In this tree:

- `mm/vmscan.c:shrink_zone()` reports reclaim deltas to `vmpressure()`;
  `vmpressure_prio()` covers high-pressure progress through scan priorities.
- `drivers/android/simple_lmk.c:simple_lmk_vmpressure_cb()` queues work at
  pressure >= 100. The callback does not synchronously wait on a victim.
- `mm/oom_kill.c` also calls `simple_lmk_oom_reclaim()` as OOM fallback.
- SimpleLMK's serialized IDLE/QUEUED/RUNNING state, freezable worker, OOM lock
  and victim accounting must remain intact. Do not add another competing killer,
  timer-based RAM sweeper or periodic cache drop.
- Do not lower kill thresholds or raise minfree merely to make a graph look
  smoother. Check app retention/reloads alongside latency.

The prior trace showed a 369.54 ms direct reclaim in a Zalo UI frame and heavy
kswapd work. That makes reclaim policy worth investigating; it does **not**
prove MGLRU fixes all stutter or that SimpleLMK caused that wait. The recorder
also overran/truncated; fresh full-window measurements are required.

## Release gates, in order

1. Choose a pinned complete donor patch series with provenance; enumerate its
   prerequisite commits. Decide on a per-node foundation port versus a carefully
   designed per-zone adaptation before changing data structure ownership.
2. Build the prerequisite layer with MGLRU disabled, preserving current reclaim
   behavior. Audit all LRU/zone/memcg users, ARM64 page flags, migration and swap.
3. Integrate real aging + eviction + refault feedback and mm lifecycle hooks.
   Build both enabled and disabled configurations; test runtime transitions.
4. Verify vmpressure/SLMK under low free memory, near-full zram, swap exhaustion,
   memcg limits, allocation failure, process exit and concurrent reclaim. Check
   no underflow/divide-by-zero, double kill, lock inversion or indefinite waits.
5. On-device tests: repeated suspend/resume on battery, charge/unplug cycles,
   recovery by command, reboot, app switching, camera/video, memory pressure,
   thermal/battery behavior and pstore for regressions. A successful compile is
   not proof these pass.
6. A/B against UI1 on equal apps/temperature: direct-reclaim duration,
   runnable delay, frame percentiles, kswapd CPU, refaults, swap usage and app
   reload counts. Accept only with measurable benefit and no stability loss.

No scheduler boost, thermal cap, OPP, KSU, suspend or recovery changes are
part of this checkpoint. Keep the existing UI1 boot as rollback. Do not label
a build "MGLRU" or "final/stable" until implementation and verification exist.
