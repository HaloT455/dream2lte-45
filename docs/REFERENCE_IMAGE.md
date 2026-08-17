# Reference image and reconstruction record

## Supplied image

| Property | Recovered value |
| --- | --- |
| File | `kernel_20260804-1643-dream2lte(20260817-035725).img` |
| Boot image SHA-256 | `cb18ff2e71e7091d9c8a7a780ddbdfb17f12656108d4b1295d86d8c2de86860b` |
| Kernel payload SHA-256 | `f76c9096fbff860a5768b03952010ceb7ce309464e58fb2647d4e3a5be7d01a0` |
| DT image SHA-256 | `078769b216aaa973f9f6aa2d7ae08d8d62461083834f6c1fb230a2f9b177d40e` |
| Kernel payload size | 35,193,176 bytes |
| DT image size | 229,376 bytes |
| Boot image page size | 2,048 bytes |
| Hardware | `samsung, SM-G955F rev05`; Exynos 8895 |
| Command line | `androidboot.hardware=samsungexynos8895` |
| Image name | `SRPPK02A007KU` |

Recovered kernel release string:

```text
Linux version 4.4.302-android13-9 (hlong@aura) (gcc version 12.2.1 20221205 (Arm GNU Toolchain 12.2.Rel1 (Build arm-12.24))) #1 SMP PREEMPT Tue Aug 4 16:42:47 +07 2026
```

## Source provenance

The closest complete source ancestor was identified by comparing the extracted
IKCONFIG, kernel subsystems, Samsung device trees and driver selections:

| Component | Revision |
| --- | --- |
| Exynos 8895 kernel base | `boloaimer/exynos-8895` commit `dcdaf6878e7f9497e1d90e25980decfa5d684f74` (`sep-16.1`) |
| KernelSU-Next | commit `a54e4fa46c6cc25bcaa055cf14d790194beffed8` |
| KernelSU numeric version | `33193` |
| KernelSU tag metadata | `v3.3.0` |
| Compiler | Arm GNU Toolchain 12.2.Rel1, AArch64 GNU/Linux target |
| Compiler archive SHA-256 | `6e8112dce0d4334d93bd3193815f16abe6a2dd5e7872697987a0b12308f876a4` |

KernelSU source is committed under `drivers/kernelsu`. Its upstream revision is
also recorded in `drivers/kernelsu/UPSTREAM_COMMIT`. The former automatic fetch
from `scripts/Kbuild.include` was removed to keep builds deterministic and
offline-capable.

## Recovered configuration

`arch/arm64/configs/exynos8895-dream2lte_defconfig` was regenerated from the
Linux 4.4.302 IKCONFIG embedded in the supplied kernel. Important recovered
features include:

- KernelSU with manual hooks
- EROFS and Incremental FS
- DM-BOW and page boost
- DPU 2.0 and Mali r19p0
- Samsung hall/force-touch and USB SS monitor support

After Kconfig normalization, all 4,517 reference symbols that exist in this
tree have matching values. The only absent reference entry is the disabled
vendor symbol `CONFIG_SEC_AVC_LOG`; 19 additional symbols resolve to disabled.

## Build verification

The tree was built from a fresh output directory using:

```text
ARCH=arm64
CROSS_COMPILE=aarch64-none-linux-gnu-
KBUILD_BUILD_USER=hlong
KBUILD_BUILD_HOST=aura
KBUILD_BUILD_VERSION=1
KBUILD_BUILD_TIMESTAMP=Tue Aug 4 16:42:47 +07 2026
```

The clean build completes both `Image` and `dtb.img`, with the exact recovered
Linux version string (including build number `#1` and timestamp).

| Generated artifact | Size | SHA-256 | Comparison with reference |
| --- | ---: | --- | --- |
| `Image` | 35,192,888 bytes | `f76faee4736040afd74eaf0b03ae34b97f0a625738a9fd1a6dcd042a8b62751d` | 288 bytes smaller (0.00082%) |
| `dtb.img` | 229,376 bytes | `6013feaf22f1f928b665447e96eab208c5847d7688a166039ff90ea7cc9e75f9` | Exact size; same SM-G955F rev05 target |

The binary hashes are not expected to match because reconstruction and manual
hook fixes change layout and code generation even where observable behavior and
metadata agree.

Compiled binaries are deliberately not committed. The supplied boot image also
is not redistributed by this repository.
