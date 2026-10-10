# K510 P14 — truthful ACPM / S2MPS17 Kbuild compatibility test

P13 CI completed green despite reporting four \`API_PORT_BLOCKED\` entries. The actual first blocker was \`No rule to make target '*.o'\`, caused by incomplete Kbuild registration in the temporary kernel tree. Hence P13 did not reach the C compiler for the imported donor files.

P14 repairs **test infrastructure** only:
- Imports the same pinned V12R5T ACPM and S2MPS17 donor files and Linux 5.10.262 baseline as P13.
- Adds temporary Kbuild object registration for four donor translation units.
- Checks each corresponding compiled object exists when a compile step returns 0.
- Classifies compiler diagnostics separately from Kbuild infrastructure failures; a missing build rule now FAILS the workflow instead of being called an API incompatibility.
- Publishes source-specific diagnostics and an honest TSV compatibility matrix.

## Explicit exclusions

No runtime ACPM IPC/firmware, no power or PMIC writes, no Exynos8895 UFS probe, no active device-tree nodes, no Android ramdisk, and **no flashable BOOT**. A C object compilation pass would not demonstrate linkage or safe device operation.

## Required next gates

1. Resolve actual C compiler missing-header/API incompatibilities and prove ACPM + S2MPS17 *linking* against Linux 5.10, while keeping hardware probe off.
2. Port proven Exynos8895 regulators/clock/UFS PHY calibration with strictly read-only UFS enumeration first.
3. Only after storage mounts and a correctly verified local V12R5T ramdisk are available, consider an explicitly experimental One UI 8 boot with backup/rollback.
