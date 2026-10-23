# SM-G955F ALICE R16 boot.img packaging — CURRENT WORKING TEMPLATE

**Update (2026-10-23): Use owner's confirmed bootable `V12R5T-Enforcing-BOOT.img`, not the earlier June 40MiB reference.** This document supersedes all earlier packaging directions for this branch.

## Exact user-provided template and verification

- File: `V12R5T-Enforcing-BOOT.img`, confirmed bootable by the owner.
- SHA256: `80c3f368ac934725aa1bae01529646c339ade3b88b656e4f98670ba71a850043`.
- Android boot v0; page size 2048; header command line `androidboot.hardware=samsungexynos8895`.
- Total 39,081,984 bytes: kernel 38,149,864, gzip ramdisk 700,389, DTBH dtb 229,376 bytes.
- Ramdisk SHA256 `0acad424dbd7eb133c8d315fad4e112a3cc1fb8991b5dafcf2949092035466a2`; contains only Android init, `dpolicy`, `fstab.samsungexynos8895`, and basic directories; **no DH2/HMP init scripts**.
- **No AVB or Samsung trailer**. Do not add an unsigned AVB footer, and do not apply `scripts/pack_alice_r16_boot.py` which targets the obsolete June reference boot.

The local reference was parsed, checked against its SHA-1 Android boot image ID, and repacked using original Image+DTB. The resulting file was **byte-for-byte equal** to the owner's bootable template; pass. A synthetic R16-labelled kernel structural test also passed (NOT a real R16 kernel and NOT flashable).

## New actual packer

Use `scripts/pack_r16_v12r5t_working_boot.py`:

```bash
python3 scripts/pack_r16_v12r5t_working_boot.py \
  --base V12R5T-Enforcing-BOOT.img --selftest
python3 scripts/pack_r16_v12r5t_working_boot.py \
  --base V12R5T-Enforcing-BOOT.img \
  --kernel Image --dt dtb.img --output boot.img
sha256sum boot.img
```

It accepts only the exact owner's reference SHA; keeps the **original ramdisk byte-for-byte**, boot parameter memory addresses, page alignment, cmdline, and hashes; inserts the compiled R16 EnergyStep Image and its matching DTBH; recomputes Android boot SHA-1 image ID; refuses missing R16 signature, broken DTB or size over conservative 40MiB cap. It produces no AVB footer, matching the owner-confirmed boot style. None of these checks prove R16 boots.

## GitHub Actions

Workflow `.github/workflows/alice-v12r69-baseline-build.yml` compiles R16. To also publish `boot.img`, manually run it with the optional `boot_template_url` input pointing to a **direct HTTPS download** of the exact `V12R5T-Enforcing-BOOT.img`, or configure the repository secret `ALICE_BOOT_REFERENCE_URL` with that private direct URL. The workflow checks its SHA, performs the exact-template selftest, and writes an additional `boot.img` and `boot.img.sha256` artifact. If the URL is empty, it only exports the compiled `Image`/`dtb.img` and does not fabricate `boot.img`.

The uploaded template is currently accessible in this ChatGPT conversation, **not automatically to GitHub Actions**. To avoid publicly hosting the boot base, a ZIP built in this conversation named `ALICE_R16_V12R5T_WORKING_BOOT_PACKAGER.zip` includes the working boot template and a verified local packer; add compiled `Image` and `dtb.img` from the R16 Actions artifact and run `bash MAKE_R16_BOOT.sh` inside the ZIP's folder.

## Safety and release

Ensure TWRP backup/rollback and check actual `BOOT` block-device capacity before flashing. This output is a **device-UNTESTED test image** even if host packing succeeds. Do not promise two simultaneous LTE registrations on the Exynos8895 by building a kernel boot image; SIM2 LTE handoff and camera must be independently tested.
