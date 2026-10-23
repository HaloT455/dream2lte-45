# ALICE S8+ SM-G955F — R16 to boot.img packaging

**Branch:** `agent/v12r69-r16-sim2-lte-ab-20261023`
**Output:** an actual Android boot image named `boot.img` (40 MiB) **only when the pinned owner reference boot is supplied**. Not a validated flashable/stable image.

## Source identity and why a boot base is required

The owner supplied a working 40 MiB `boot.img`, SHA256 `9012313ab3d8b2e15fe00871da4872d4d09f7068211b36604eede6fe138c646b`. It contains a boot-v0 header, special Exynos8895 ramdisk `/init`, vendor `fstab.samsungexynos8895`, `dpolicy`, original DTB, `SEANDROIDENFORCE` marker, and **signed AVB vbmeta footer**. A plain R16 `Image` and `dtb.img` are *not* a boot image. The original `init.rc` configures legacy `interactive` governor and two DH2/HMP shell scripts, conflicting with later R16 EnergyStep.

`scripts/pack_alice_r16_boot.py` uses ONLY that SHA-pinned reference, retains init/fstab/dpolicy, removes old DH2/HMP scripts and legacy interactive init.rc, inserts the kernel-built R16 `Image` and `dtb.img` into the correct boot-v0 offsets, recomputes boot SHA-1 ID, places Samsung trailer, and regenerates the AVB hash footer with **algorithm NONE** using official Android avbtool. Exact result is padded to the 40MiB boot partition.

**Security and platform caveat:** AVB algorithm NONE is unsigned. Old signed vbmeta cannot be retained when the image content changes, and its original signing key is unavailable. This image may fail on a locked bootloader or under strict verified-boot policy. Use ONLY on an already-unlocked development device after confirming a backup/TWRP recovery path. A generated image does not prove kernel boot, radio or camera function.

## GitHub Actions automatic artifact

Workflow: `.github/workflows/alice-v12r69-baseline-build.yml` on this branch. Build compiles R16 and produces the source artifact containing `Image`, `dtb.img`, `SHA256SUMS`, etc.

For the **additional boot.img artifact**, manually run `workflow_dispatch` with the optional `boot_template_url` input pointing to the owner's **direct-download** reference `boot.img` served over HTTPS; or configure `ALICE_BOOT_REFERENCE_URL` as a repository Actions secret containing a private signed HTTPS file URL. Source must match the known SHA256; otherwise build fails closed. This file was supplied only inside ChatGPT and **does not exist automatically inside GitHub Actions**.

When supplied, extra artifact appears as:

`ALICE-S8P-R16-SIM2-BOOT-UNSIGNED-UNTESTED-<commit>`

and contains `boot.img`, `boot.img.sha256`, `paired-contract.json`. The existing R16 kernel artifact continues to publish standalone Image/dtb as before. If the source URL is missing, the workflow reports "BOOT.IMG NOT PACKAGED" and **does not create a fake boot.img**.

Alternatively, the owner can use the locally supplied conversation ZIP `ALICE_S8P_R16_BOOTIMG_PACKAGER_REFERENCE.zip` which contains their exact reference boot and offline packing script. It requires unpacking the successful R16 Actions kernel artifact (Image and dtb.img) locally and running `bash build_boot_local.sh Image dtb.img`. This avoids exposing the user reference boot to a public GitHub repository.

## Confirmation gates

1. Verify exact SHA of reference boot and image size (40 MiB), review unsigned AVB and boot-v0 header fields.
2. Have backed up current working boot image; verify restore under TWRP.
3. Test whether S8+ actually boots R16, camera still previews and records, SIM1 still reaches LTE and SIM2 has service, before any LTE role switching.
4. **No claim of 4G+4G simultaneous service:** Exynos8895 hardware capability remains unverified; setting LTE mask 9,9 is not a dual-LTE modem unlock.

No EFS/NV/CP, IMEI, baseband or camera binary is changed by this packaging tool.
