# P19: Samsung Exynos8895 vendor UFS → Linux 5.10 real API port (in progress)

Base: P18 original Linux 4.4 vendor UFS compile fails against Linux 5.10 with structural API differences. We preserve the original Linux 4.4 file in a *quarantined temporary build path* and only apply changes justified by real 5.10 headers and behavior. **No fake stub, skipped SMC security call, or runnable boot image is permitted.**

## Implemented

- Automated one-to-one mapping of three UFS UniPro L2 timer identifiers from vendor 4.4 to native Linux 5.10, asserting each new macro exists in original Linux 5.10 headers.
- Re-run actual AArch64 C compilation for original Samsung source with pinned power, CAL, M-PHY and UniPro headers.
- Preserve all fatal compiler diagnostics and positive/negative classifications; an audit SUCCESS does not mean driver compile success.

## Hard blockers still requiring implemented semantics

1. Samsung secure monitor: `exynos_smc`, `SMC_CMD_FMP_SECURITY`, `SMC_CMD_SMU`, `SMC_CMD_LOG`. No-op replacements risk inline crypto/integrity and storage corruption. **Do not bypass.**
2. `ufs_hba_variant_ops`: map `host_reset`, `pre_setup_clocks`, `setup_clocks`, nexus and UIC callback logic to Linux 5.10 with strict order and arguments.
3. 4.4 quirk flags must be interpreted and translated to correct native host mechanisms; do not assign numeric bits blindly.
4. `pm_qos_*` and device throughput constraints: use real Linux 5.10 PM QoS/ICC APIs appropriate to Exynos8895.
5. Exynos8895 M-PHY calibration tables, clocks, Samsung Speedy + S2MPS17 + ACPM mailbox firmware runtime validation.
6. `ufs_hba` private fields and transfer function signature differences.

## Graduation criteria

**C compile and vmlinux final link are required but not sufficient for BOOT.** An actual Samsung vendor UFS source compile FAIL remains explicitly FAIL even if the compatibility audit workflow succeeds. No Flash until separately approved runtime/backup gate and UFS enumeration in a read-only controlled environment.

Evidence: see GitHub Actions `k510-p19-vendor-ufs-port.yml` and its `vendor-ufs-result.txt`.
