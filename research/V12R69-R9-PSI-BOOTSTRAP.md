# R9: PSI bootstrap accounting and original worker member offsets

R8 reached the Samsung logo and rebooted on the user's SM-G955F. A private
TWRP read of the first 39,081,984 bytes of BOOT matched the delivered R8 image
exactly. The captured last_kmsg contains S-Boot loading Recovery, not an R8
Linux panic. Neither a crash stack nor the reboot's root cause was recovered.
R8 must therefore be treated as a failed device boot, despite successful CI.

## Reproduced source defect

The 4.4 scheduler calls psi_init() during sched_init(). rest_init() then forks
and enqueues init and kthreadd before early/core initcalls. Deferring
psi_initialized until a core initcall skips those enqueues. Their first
dequeues after activation still decrement the zero per-CPU running counter.

The new regression compiles the actual psi_init(), psi_task_change(),
psi_group_change(), test_state(), and group iteration functions. On R8, the
two boot task dequeues produce psi_bug=1 and NR_RUNNING=4294967294. On R9,
enqueues/dequeues remain balanced at zero with psi_bug=0. This establishes a
source accounting defect; it does not establish the missing crash's cause.

R9 enables accounting immediately after PSI group initialization, before
the first normal task is created. The existing system_wq guards remain at
both averaging and pressure-trigger queue sites. The regression exercises
early accounting with no system_wq, then normal accounting and pressure
trigger activation after workqueue creation. The PSI-disabled path remains.

## Worker layout

R8 inserted the new last_func field in the middle of struct worker, moving
current_pwq from byte 32 to 40 and task from byte 64 to 72 on 64-bit systems.
R9 appends the field instead, preserving every original member offset and
the documented cacheline boundary. Allocation still uses sizeof(*worker).
The new test compiles the real declaration and checks the original offsets.
This removes an unnecessary layout change; no external consumer fault was
observed in the device logs. The idle PSI shutoff functionality is retained.

## Scope and validation limits

MGLRU remains OFF by default. EAS/EnergyStep settings, GPU -5 load bias,
native thermal/QoS/clock constraints, KSU 32590, and Enforcing are unchanged.
Schedutil and resident AI remain removed. The same R8 manual LRU/GPU APK is
reused because its code has not changed. The one-shot LMKD module accepts
the explicitly supported R8 and R9 kernels; its post-boot guards remain.

Host checks and ARM64 CI can validate compilation, accounting behavior, and
packaging. They cannot establish physical boot, Home/SystemUI stability,
temperature, or battery results. R9 is a candidate repair of demonstrated
source defects. The Samsung-logo reboot root cause remains unconfirmed.
