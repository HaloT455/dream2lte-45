# R14 boot compatibility

Create an owned `/dev/cpuset/sf` group with the same 0-7 CPU eligibility and root
memory-node mask. Hash failures/unknown JSON no longer suppress this setup.
Only UID1000 SurfaceFlinger currently in the root cpuset with 0-7 affinity is
moved. Explicit ROM placement, a foreign sf group and restricted affinity are
preserved. The per-boot ownership marker lives on /dev tmpfs.

Known original task-profile JSON still receives only the two audited GPIS
WriteFile changes. Unknown JSON is never edited. Hash command exit status and
64-character digest format are checked with explicit platform tool paths;
the observed digest is logged. Setup has bounded post-fs-data, SurfaceFlinger
restart and boot-completed actions, with no polling daemon or framework restart.
Root cpuset masks, thermal limits, OPP voltages, GPU boost and MGLRU defaults
are not changed by this setup.

R14 also enables VM event counters and appends all-zone pgscan/pgsteal aliases
to /proc/vmstat. The legacy per-zone fields remain intact. Alias values come
from the same all_vm_events snapshot, allowing Android LMKD to observe actual
reclaim rather than absent counters. LMKD kill thresholds are not modified.

Host fixtures execute the embedded script and compiled aggregation routines.
They do not establish on-device boot success, SELinux access, frame-time or
battery improvements. Kernel boot retains the R13 guarded Power HAL bootstrap.
