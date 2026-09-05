# V8: carry forward the bootable V6 baseline

The user supplied `dream2lte-S8Plus-V6-UI1-Trace-Enforcing-b70a07db.img`
and confirmed that it boots. Its kernel identifies the UI1-Trace build from
`b70a07db8b6b5d08beeb3c910a9c731b5cee941b` (`agent/ems-v5-ui1-trace`).
V8 at `f161ff4e2344f4a64f00546c106b45ef94b6139a` forked before several
stability fixes in that branch. This change carries those fixes forward.

## Evidence and changes

| Area | Previous V8 | Restored baseline |
| --- | --- | --- |
| Watchdog suspend/resume | Platform device PM callbacks; disables/masks watchdog in suspend | Exact V6 syscore path from `0cf34d3a` |
| Schedutil workers | Both cluster workers pinned to CPU0 | Per-policy CPU affinity from `3890699b`, with exact UI1 worker coalescing |
| SimpleLMK | Sets TIF_MEMDIE on threads without regular OOM victim accounting | V6 `a534381d`: serialize with `oom_lock`, respect OOM disable, use `mark_oom_victim()` once per process |
| Recovery reboot | Loses requested reboot command in SoC reset handoff | Exact V6 recovery target preservation from `6ede20ab` |
| UI scheduling | CPU-group fallback hints missing | UI1 `887e9cc5` policy and native SchedTune precedence restored |
| Trace capture | Event tracing and debugfs not present in built config | Same minimal event-tracing configuration as the supplied boot |

The SimpleLMK source now differs from V6 only by the legacy `adj` parameter
needed for the Android lmkd handshake. The V8 hard-reset-key fix is retained:
holding the keys must not deliberately call `BUG()`.

MGLRU remains compiled and enabled. Its per-zone reclaim and MM lifecycle
hooks are retained, including both `lru_gen_switch_mm()` calls in scheduler
core. The defconfig differs from V6 only by the five MGLRU options; CI sets
the release string and the selected SELinux variant separately.

This is a restoration of the tested device baseline, not a wholesale
replacement of Samsung hardware support with unrelated scheduler code.

## Boot payload comparison

| Supplied V6 component | Size (bytes) | SHA-256 |
| --- | ---: | --- |
| Complete boot image | 39065616 | `000058d6a47f2521027f2b56d79294e411fbebafb8db5b943f8caa25ecd7ed83` |
| Kernel Image | 38131944 | `bdea81eefc55a83f15fd8fdf929479ba44d2444d136b02c09f2ed5d60b6e79ea` |
| Ramdisk | 700389 | `0acad424dbd7eb133c8d315fad4e112a3cc1fb8991b5dafcf2949092035466a2` |
| DTB | 229376 | `d3907f8e50d3d66c193eb800bafdc20e356bdb400ccefc140074cfe92c155c20` |

The previous V8 DTB already matches V6 byte for byte. The boot header uses
2048-byte pages, `androidboot.hardware=samsungexynos8895`, and the Samsung
DTB-size field. AnyKernel3 remains pinned to its existing revision and
repackages the installed boot with the new Image and matching DTB; it keeps
the ROM's ramdisk. Package names include `V6Base` to distinguish this build
from the earlier V8 candidates.

## Validation and limits

The restored CPU UI and schedutil host checks pass locally. CI runs them,
checks the exact V6 platform-file hashes, enforces the restored trace config,
builds Image and DTB for both SELinux variants, and compares the resulting
DTB against the supplied V6 hash. CI artifacts contain the source revision,
kernel config, System.map and checksums.

The available short Android logs do not establish which missing fix caused
the restart. Successful compilation and package validation cannot prove
hardware boot, screen-off resume, or recovery behavior. These still require
testing the new ZIP on the phone, starting from the known-working V6 boot.
This change makes no new claim of SIM2 LTE/VoLTE/VoWiFi or AOSP runtime
support; those require modem, ROM/IMS and device verification.
