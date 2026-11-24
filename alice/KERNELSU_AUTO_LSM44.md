# ALice S8+ — KernelSU auto LSM hooks on Linux 4.4

## Why this changed

The donor Aura Android 13 `boot(1).img` contains
`CONFIG_KSU_LSM_SECURITY_HOOKS=y`, but it does **not** carry the source of
those hooks. The ALice tree already contains KernelSU (from
`HaloT455/KernelSU`) and had `CONFIG_KSU_LSM_SECURITY_HOOKS=n` plus
five direct, manual hook call sites in `security/security.c`.

Simply setting the Kconfig option to `y` would produce duplicate
observers, and the existing 4.4 implementation of
`drivers/kernelsu/hook/lsm_hooks_list.c` modifies the function pointer
of the first registered LSM handler. That is not the safest way to
integrate KernelSU on this device.

## New 4.4 implementation

- `CONFIG_KSU_LSM_SECURITY_HOOKS=y` is enabled in
  `arch/arm64/configs/exynos8895-dream2lte_defconfig`.
- `ksu.c` uses `hook/lsm_hooks_register_44.c` on Linux 4.4 only.
  Other kernel versions retain their original upstream/downstream paths.
- The five original KernelSU observer operations
  (`bprm_check_security`, `inode_rename`, `task_fix_setuid`,
  `file_permission`, `setprocattr`) are added to the actual
  Linux 4.4 LSM `security_hook_heads` list. These callbacks are
  registered **ahead of** the regular LSM callbacks to preserve the
  prior manual-hook precedence; the existing SELinux callbacks remain
  installed and continue to enforce their policies.
- All six `#ifdef CONFIG_KSU` sections in `security/security.c` — one
  declaration block and five manual call sites — are gated to execute
  only when `CONFIG_KSU_LSM_SECURITY_HOOKS` is **disabled**.
- No SELinux callback is overwritten; no read-only kernel memory
  patch or syscall-table hook is enabled.
- The high-frequency boot-only `file_permission` observer is removed
  from its own LSM list after KernelSU stops the startup VFS-read
  handler. The cleanup worker uses `list_del_rcu()` and
  `synchronize_rcu()`. If worker creation fails, the hook remains
  installed with its guarded `ksu_vfs_read_hook` check, so that failure
  does not silently remove boot functionality.

`CONFIG_KSU_THRONE_TRACKER_ALWAYS_THREADED` remains **disabled**.
This is intentional: the KernelSU source warns that threaded
first-run throne tracking can cause early-boot failures on FDE/FBEv1.

## Reproducible checks

`python3 scripts/test_ksu_auto_lsm_44.py` actually compiles the
registration code on a host with mock Linux 4.4 LSM list heads. It
checks exactly five callbacks, exactly one observer invocation each,
the absence of readonly-slot hijacking, and RCU removal of the
boot-only file-permission callback. This is not hardware boot testing.

CI also verifies actual `out-ea/.config` values and checks
`out-ea/System.map` for the compiled `ksu_auto44_bprm_check` and
`ksu_auto44_release_vfs_hook` function symbols, while preserving
the Samsung A53 EGO/Exynos8895 energy_aware-only config.

On a rooted device, first verify full boot and that KernelSU Manager
recognizes the kernel. Diagnostic commands:

```sh
su -c 'dmesg | grep -i "kernelsu: registered"'
su -c 'dmesg | grep -i "kernelsu: removed boot-only"'
su -c 'cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor'
```

No net battery-life, speed, root reliability or boot-compatibility
improvement is claimed until this is tested on an actual SM-G955F.
Keep an original `boot.img` backup and a recovery path.

## Not imported from Aura

- No swap to `interactive`, `blu_active` or HMP.
- No weaker thermal throttling or lowered CPU max OPPs.
- No forced always-threaded throne tracker.
- No unverified Mali Vulkan Boost/MPTCP/Freecess binary features.
- Aura's EROFS fstab is still opt-in under
  `alice/rom-profiles/aura-android13-erofs/` and is not injected into
  the default ramdisk.
