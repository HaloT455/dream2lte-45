# Screen-off reboot audit

## Evidence from the 2026-08-29 logcat

The captured log stops about five seconds after the power button turns the
display off. It shows Android entering autosuspend, a native suspend-counter
wakelock, a failed Wi-Fi `SETSUSPENDMODE 1` command, and repeated attempts to
write the root `/dev/cpuset/cpus` mask. It does not contain a kernel panic,
OOM, SimpleLMK kill, or thermal shutdown record.

## V6 comparison

| Area | Known-good V6 | Failed SuspendFix build | SleepStable decision |
| --- | --- | --- | --- |
| Samsung watchdog | Late syscore suspend/resume | Converted to platform device PM | Restore V6 syscore path exactly |
| Schedutil worker affinity | Each worker uses its policy mask | Both cluster workers forced to CPU0 | Restore per-policy binding |
| SimpleLMK | Not present in the original reference image | Enabled in the tested build | Keep for isolation; log has no LMK/OOM failure |
| Root cpuset writes | Root cpuset is read-only in the V6 kernel too | Same kernel behavior | Do not weaken the root cpuset invariant |
| Wi-Fi suspend command | Broadcom driver implementation unchanged | Same driver implementation | Do not change without a kernel/pstore failure trace |

The root cpuset error and Wi-Fi command failure are compatibility warnings,
but neither was introduced by the latest kernel commit. Changing either from
one short logcat would add new suspend risk. The first test build therefore
reverts only the two post-V6 changes that directly altered screen-off kernel
execution.

## Required next capture

After any subsequent unexpected reboot, collect `/sys/fs/pstore/*` and
`/proc/last_kmsg` before rebooting again. This tree already enables pstore,
pmsg, ramoops, Samsung last-kmsg, and Samsung reset-reason support.
