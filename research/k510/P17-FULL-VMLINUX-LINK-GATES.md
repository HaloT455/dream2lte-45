# K510 P17 – Full-vmlinux linkage of ACPM / S2MPS17 into Linux 5.10.262

Target Samsung SM-G955F, Exynos8895, Android 16 One UI 8. This is an **unflashable lab** following the P16 6/6 source compile and \`ld -r\` results.

## Criteria (do not confuse layers)

- **P16:** 6/6 donor C objects compile, relocatable aggregate link succeeds; **NOT** real kernel link.
- **P17:** Stage the same pinned V12R5T files and exact 5.10.262 Linux source in ephemeral CI; add a REAL \`CONFIG_EXYNOS_ACPM=y\` in \`drivers/soc/samsung/Kconfig\` (not KCFLAGS) and put all six drivers into the final built-in Kbuild tree.
- Compile and link **\`vmlinux\`**, then compile \`exynos8895-dream2lte.dtb\`. Do not publish kernel \`Image\`, BOOT or flash ZIP. Verify \`vmlinux\` is an AArch64 ELF and \`System.map\` defines critical ACPM/PMIC interfaces.
- **Failure must remain failure** if any undefined reference, missing symbol, missing config, DT incompatibility or linking error occurs. Logs are always uploaded.

## Not addressed yet

Linux 5.10 board ACPM firmware mailbox protocol, realtime power regulator sequencing, PMIC IRQ behavior, Exynos8895's vendor UFS/PHY/UniPro calibration, Android One UI 8 boot ramdisk/fstab, SELinux/vendor/HAL are NOT validated by linker success.

The donor's original ACPM initcalls might access physical resources during boot; **even a fully linked P17 image must never be flashed or distributed as a boot image without a separate DT/firmware, runtime and rollback review**.

## Artifacts

CI artifact is named \`ALICE-K510-P17-FULL-VMLINUX-GATE-NO-FLASH\`. It contains only compiler/linker diagnostics, configuration and verification manifests. No runnable kernel binary will be uploaded.

Recommended P18 gate: audit all unresolved runtime PMIC/ACPM dependencies, validate Exynos8895 UFS host clocks+PHY+regulator supply graph, and design a separate read-only boot probe with verified local recovery backup (approval before flash).
