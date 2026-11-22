# ALice S8+ EnergyAware boot.img CI

This path is deliberately **missing** the original user ramdisk until uploaded.
The verified `boot.img` must use the exact original ALice Galaxy S8+ ramdisk.

## Required input

Upload a file named **ALICE_original_ramdisk.cpio.gz** into this directory.
SHA-256 must equal:

```
0acad424dbd7eb133c8d315fad4e112a3cc1fb8991b5dafcf2949092035466a2
```

## What happens automatically

On the push that adds the input, GitHub Actions runs
`.github/workflows/alice-s8plus-boot-img-ci.yml`.
It fetches the actual, verified arm64 kernel and Samsung DTB from the
successful build run [45043851949](https://github.com/HaloT455/dream2lte-45/actions/runs/45043851949),
reconstructs the original Android boot v0 header, and writes
`output/boot.img`. CI **refuses** other ramdisks and publishes only if
the final SHA-256 is exactly:

```
4173a9b5b4c497070369913369ceabb5682457194343d0e02409f63dc3a3fa08
```

The GitHub Actions artifact will be called
**ALice_S8Plus_EnergyAware_KSU_LZ4KD_BOOT_TEST**.

This is **not physically boot-tested**. Do not flash without a backup and
recovery method. This energy_aware is an Exynos8895 adaptation, not the
complete Samsung A53 EMS/EGO subsystem.
