# ALICE V12R69 R3: repair status

## Current result

R3 includes every saved R2 source change and six additional defect groups.
35/35 host commands passed. No ARM64 kernel, boot image or APK was built;
no handset installation, runtime stress test or remote push was performed.
The user's requirement to finish repairs before building remains in effect.
This is a source repair package, not a flashable image or a claim that all
S8+ performance symptoms have disappeared.

## Additional R3 repairs

1. **Reclaim budget:** cap consumed work at the budget before unsigned
   subtraction. Skipped-page scanning, the fallback type or a compound page
   can exceed one batch. R2 wrapped `budget - consumed` and kept reclaiming
   despite the intended bound. Preserve the per-call reclaim target.
2. **Direct reclaim:** restrict the background retry cooldown to kswapd.
   A task allocating memory may reclaim newly eligible pages immediately,
   rather than being rejected by a cooldown from an earlier background scan.
3. **PTE and rmap aging:** this 4.4 generic PTE callback holds no table lock.
   Use a PMD callback that holds the PTE lock across mapping lookup, page
   pinning and access-bit clearing. Skip unstable/huge PMDs without splitting.
   Recheck MGLRU state, generation, per-type eligibility, LRU membership and
   memcg before clearing young bits. Reject non-normal mappings in both
   walkers. Page-table and scan-around aging remain explicit opt-in.
4. **PSI monitor baseline:** collect existing per-CPU pressure under the
   update lock before creating a monitor window. Uncollected pre-registration
   pressure must not become a new monitor event.
5. **PSI average backlog:** keep the cumulative sample in u64. A backlog
   above 2^32 nanoseconds must be clamped to the sampling period before any
   narrowing can discard pressure.
6. **EnergyStep tunables:** update each directional rate delay and its minimum
   gate together under the policy update lock used by scheduler readers.
   Remove the unrelated mutex that did not serialize those readers. Convert
   microseconds in u64 before multiplication.

The app feature list also reads the kernel's actual MGLRU state instead of
asserting a default OFF value. New checks are registered in both source-only
CI and the manually dispatched baseline workflow.

## Previous R2 repairs retained

* EnergyStep worker shutdown, bounded latest-target replay, policy snapshots,
  initialization cleanup and driver-error cache invalidation.
* Serialized concurrent MGLRU ON/OFF writes and disabled-generation guarding.
* PSI average/read cadence, deadlines, pending activity, short samples and
  pressure-trigger input handling.
* Samsung/AOSP thrashing-property selection and exact failed/interrupted
  rollback handling in the app helper.
* Binary-scoped, reversible Samsung low-swap property repair, including
  reference-swap normalization and second-level properties. It confirms the
  reported effective threshold and rolls back failed application.

The low-swap helper pins supplied LMKD SHA256
`3bbca06f1f7dcc1be36b7e16d70e6ffe833fe420bab7a380b8582e3f3a822b49`.
It is explicit, changes volatile RAM properties only, and does not change
swap size, compression ratio, kill scores, governor or MGLRU. It has not been
applied to the handset, whose installed binary identity remains unverified.

## Verification and its limits

New host tests compile extracted production C functions, with mocked kernel
primitives, and execute reclaim overshoot, cooldown, PTE locking/OFF races,
PSI backlog/baseline and policy-tunable cases. The R2 source controls fail the
new tests; repaired source passes. Existing 32 host commands plus three new
scripts all pass. Shell transaction checks remain mocked; they do not execute
the Samsung LMKD binary. These checks do not emulate full kernel scheduling,
physical page lists, Exynos DVFS, swap I/O or Android UI rendering.

## Device evidence still unresolved

The supplied V12R68 capture reports MGLRU state 0. SystemUI PID 6152 reports
up to 694 skipped frames; Launcher PID 6727 up to 203. The capture has 90 LMKD
Reclaim entries for 71 process names; this is not proof of 71 killed apps.
No Launcher am_proc_died event was found. Raw SwapFree alone does not represent
the LMKD effective-swap calculation. Samsung's 72-percent reference policy
becomes approximately 78 percent on the observed 3.2-GiB swap configuration.

The existing vendor Test7 image was inspected without modification. Its
boot-completed RAM expansion action tries to activate already-active zRAM.
That duplicate activation was not established as the cause of sustained UI
stalls, so no vendor image was rebuilt from this assumption.

Hardware UI latency, app retention under pressure, MGLRU toggling under load,
thermal behavior and repeated reboot stability remain unverified. There is
no ADB connection to the user's S8+ in this environment. Previously rejected
remote publishing was not retried or bypassed.

## Source lineage

Remote base: 509bc47a4e448a066d1ff84e672f40d38e0fc325.
R2 was restored from ALICE_V12R69_SOURCE_FIXES_R2_20261012.zip;
its original local head was dd7e7c5efdc8674ac62b13aec00cebb7ed2ed17b.
The cumulative R3 patch applies directly to that remote base; the incremental
patch applies to the saved R2 contents.
