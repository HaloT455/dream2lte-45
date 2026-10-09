# Alice K510 P2F — Samsung SM-G955F boot format verified

**Target:** Galaxy S8+ SM-G955F rev05, Exynos8895.
**Source:** known-good 40 MiB BOOT backup captured 2026-10-10.
**Known-good kernel:** Linux 4.4.302-Alice-V12R5T. Never overwritten.

## Results

- P2C *integrated Linux 5.10.262 + custom dream2lte uniLoader* compiled in [CI 37999002645](https://github.com/HaloT455/dream2lte-45/actions/runs/37999002645). Compile success is not hardware boot.
- Legacy Android BOOT header page size = **2048** bytes, with `kernel_size=38149864` and `ramdisk_size=700389`.
- Samsung original has **DTBH v2** at offset `38852608`, declared size `229376` bytes; the FDT inside has byte length `227317`.
- DTBH entry: Exynos `8895`, platform code `0x50a6`, subtype `0x217584da`, hardware revision **10 through 255**, FDT offset **2048**, padded FDT size **227328**, record terminator **0x20**.
- A separate identical DTBH copy follows later in the old BOOT partition. It may be obsolete tail data; its role with Samsung S-Boot has NOT been established. Do not blindly preserve or remove it on a newly constructed image.
- The old `SEANDROIDENFORCE` marker exists. An AVBf-looking marker at end of the partition has inconsistent pointers and has not been authenticated.
- **Local bytewise test:** Reconstructing the primary DTBH from the original embedded FDT using the Exynos-8895 header values yielded an exact **229376-of-229376-byte match** with original DTBH. The private 40 MiB BOOT copy was not committed to GitHub.
- `p2f-dtbh-pack.py` generates DTBH **only**, for CI-style compilation/research.
- `p2f-verify-stock-local.py` checks round-trip equality on the user's machine only, with no device writes.
- Synthetic FDT/DTBH GitHub Actions tests passed in [CI 38000881696](https://github.com/HaloT455/dream2lte-45/actions/runs/38000881696).

## Independent public references

- uniLoader: https://github.com/ivoszbg/uniLoader
- Galaxy S8 barebox S-Boot handoff and bootimg example: https://lists.infradead.org/pipermail/barebox/2025-July/051865.html
- Samsung Exynos boot image + DTBH tooling: https://github.com/TwrpBuilderTests/android_device_samsung_dreamlte/tree/master/dtbhtool

## Why a flashable boot.img is still blocked

1. Must validate SM-G955F S-Boot -> uniLoader physical relocation; legacy `kernel_addr` not proven a real runtime pointer, and Samsung applies DT overlays.
2. Must validate firmware and early clock/power/PMIC handoff. P2B only compiled its board profile with unverified DECON/PMIC writes disabled.
3. Must port/exercise a durable **early debug channel** (UART or persistent pstore/ramoops) before first uncontrolled boot test; userspace `/init` heartbeats alone won't survive kernel freezes.
4. For actual Android 16 later, must port UFS storage + PHY + regulators, display, USB and vendor/HAL stack.
5. Before controlled testing, confirm recovery (Download Mode / Odin or Heimdall), intact V12R5T BOOT backup and rollback plan. Build experimental image only as a clearly labeled research artifact once static structural and hardware prerequisites are met.

**P2F validates the Samsung DTBH format only, not a usable boot.img. Do not flash P2F files.**
