# R7: concurrent reclaim and I/O boost expiry

Trigger reported on R6: launch a second application, then return to Home or
pull down the notification shade. The phone lags, can freeze, and becomes hot.
No R6 crash trace was supplied. The older launcher log contains only
`error: closed`; the older thermal snapshot is R4 with MGLRU disabled.
Neither establishes the current failure's cause.

## Source defects corrected

- EnergyStep reset old I/O boost only on non-I/O callbacks. A separated I/O
  wakeup could double a stale boost, or retain it when a request was pending.
  Expire first, then restart the burst at the policy minimum. A shared cluster
  also expires a sibling's I/O boost after a tick independently of its longer
  WALT utilization sample lifetime. Sustained I/O still ramps, and normal
  utilization, frequency tables, policy bounds and thermal protection remain.
- MGLRU updated NR_ISOLATED counters but never used the native 4.4
  too_many_isolated check. Check before another batch, wait once outside the
  LRU lock, then recheck. Persistent saturation returns zero real progress;
  the caller may try the other type. Preserve native kswapd, sane-reclaim and
  relaxed NOIO/NOFS threshold behavior. This is a bound per batch, not a
  global bound on an allocation's reclaim latency.
- MGLRU collected writeback/congestion statistics from shrink_page_list but
  discarded the classic 4.4 zone flags and I/O throttling feedback. Share the
  original classic feedback function between both paths. Run it after pages
  are returned and isolated counters are balanced, without the LRU lock held.

Reference for I/O expiry semantics (R7 does not restore the schedutil governor):
https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/refs/tags/v5.2-rc7/kernel/sched/cpufreq_schedutil.c

## Validation and remaining limits

The new tests compile and execute actual C functions from these sources with
deterministic pageout/I/O stubs. Run them against R6 to confirm they reject
the missing behaviors. They cover pending stale requests, shared CPU expiry,
burst ramp/decay, saturated isolation, progress on the other page type,
counter balance, NOIO/legacy memcg exemptions and slow writeback feedback.
They cannot validate physical boot, Mali/ION, Launcher/SystemUI responsiveness
or thermal improvement.

MGLRU remains default ON, deferred PTE walks remain OFF, AI workers remain
removed, and EnergyStep remains the default. Schedutil remains absent. No
RAM flushing, background force-ON loop, thermal override or frequency cap is
introduced.

`scripts/capture-r7-host.sh` streams a bounded, read-only capture to a Linux
adb host while the reported gestures are reproduced. Already received logs
survive a phone hang. Captures include actual kernel/governors/LRU state,
frequency residency, PSI/reclaim/swap counters, temperatures and UI process
wait stacks, plus kernel and Android system/event/crash logs. This is manual
diagnostics; it is not an APK service or automatic upload.
