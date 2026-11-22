# REAL Samsung Galaxy S8+ (Exynos8895) energy_aware boot CI

There is **no pre-generated boot.img in this branch**. The energy-aware CI
will only publish a flash-test boot image when supplied with a **genuine**
original boot image from the same handset and currently used ROM.

## Required file: choose ONE

- `boot-input/ALICE_original_boot.img` (original unmodified boot partition image), OR
- `boot-input/ALICE_original_boot.zip` (ZIP containing exactly one file
  named `boot.img`, with the same original image bytes).

The boot input is NOT included in the repository. Do not substitute a random
downloaded Galaxy S8/S8+ boot or a reconstructed/empty ramdisk. Kernel/ROM,
ramdisk, DTB and boot header must all match the target handset. Upload only
material you are authorized to use; avoid committing personal boot dumps to
public repositories if they may contain private data.

## What the CI actually does

1. Checkout the exact `agent/s8plus-a53-ego-esg-port-20261123` commit.
2. Compile **energy_aware** as the default governor with
   `exynos8895-dream2lte_defconfig`.
3. Verify `System.map`, `.config`, `Image` and the Samsung `dtb.img`
   from the **same build**, not a hardcoded previous run.
4. Validate original `ANDROID!` boot v0, Exynos8895 command line and
   `DTBH` DTB layout. The repacker preserves original header fields,
   ramdisk, second-stage and recognized Samsung `SEANDROIDENFORCE` trailer,
   replacing only kernel + Samsung DTB + boot SHA1.
5. Record source-boot SHA256, new Image SHA256, DTB SHA256, preserved ramdisk
   SHA256, final boot SHA256, commit SHA and matching kernel config.
6. Publish `ALice-Exynos8895-EnergyAware-REAL-BOOT-<sha>` artifact **only
   when every check passes**.

If original boot input is missing, kernel CI still builds `Image` and
`dtb.img`, emits a warning, and **does not create a boot image**.

The separate manual `alice-s8plus-boot-img-ci.yml` workflow also refuses
stale builds. It can only download an energy-aware kernel artifact from a
successful CI run for the **exact same commit**.

## Safety and status

No image produced by this CI has been confirmed to boot on physical hardware.
The custom kernel is not signed; do not bypass a locked bootloader, Verified
Boot, or device security. Preserve your original boot partition, maintain
working recovery and verify the target partition size before any flash.

This is an Exynos8895 Linux 4.4 energy-model adaptation inspired by Samsung
EGO/EMS. It is not a full port of Samsung Exynos1280 scheduler hooks.
