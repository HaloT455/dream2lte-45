# ALice unified source — Galaxy S8+ dream2lte

Target: Exynos 8895, One UI 8 / Android 16 port. This branch consolidates the kernel, Android AliceDrop and vendor tools. It is a source integration, NOT a claim of full hardware compatibility.

## Verified source ancestry
- Kernel: 43d3e88f61af2e8e187fd6a3c52514113a2229c1; kernel CI 45432352868 succeeded.
- AliceDrop 0.4 sender: 1a9aeb013413522cb99883d9c551f2cfd5e9cafc; APK CI 45659053524 succeeded. Native protocol CI 45555705240 succeeded.
- Vendor audit/merge tool: 424f260a09e57c891c1c334c5ae8183b822440ac; synthetic filesystem CI 45667502494 succeeded.
- The vendor branch is already a descendant of both earlier branches (compare behind_by=0); no cherry-pick, squash or force push necessary.

## Build outputs and limitations
- Kernel CI preserves existing energy-aware configuration, adaptive OC, KSU and LZ4KD checks. A genuine device boot image is required for repacking; otherwise the output is kernel only.
- AliceDrop CI builds its pinned upstream ARM64 FFI from source rather than relying on the older expiring artifact. No AWDL backend validated for BCM4361; native iPhone file transfer and touch-to-share remain unverified.
- The November 26 input set is recorded in `s8plus-inputs-20261126.json`. The real `vendor.new.dat.br` reconstructs to a 600 MiB EROFS partition image (1,376 entries); Test7 is the reference donor (1,429 entries). Preserve the new.dat radio stack; Dual SIM work is deferred.
- Retain the EGO adaptive OC governor and its state aliases from `alice-unified`; the paired branch's EROFS, RGB LED, PSI and disabled-kernel-LMK gates are integrated without reverting those governor changes. The manual boot repacker now requests the actual artifact name emitted by kernel CI.
- Actual input EGO config matches the prior unified CI config, and its DTB is byte-identical. Kernel Image bytes differ between builds; this is not claimed to be bit-for-bit reproduction of the input kernel. New builds include the kernel ELF and exact source commit for further audit.
- The real new.dat-based vendor source is reproducible on `HaloT455/Vendor-45-`, branch `work/s8plus-newdat-unified-20261126`, commit `7c0f966009db44cebc302db87c27c529e4a872df`. It includes verified file deltas against immutable Test7, original Android metadata and the reviewed overlay. The local image has passed complete extraction/metadata verification; its CI builds the same source.
- The actual uploaded EGO boot is retained as checksum-pinned ZIP parts on that immutable vendor commit. Kernel CI retrieves it, verifies SHA256 `c09f62145c47926a423114a525ae695e10a127f4e8015f697082abd969729873`, then preserves its ramdisk while inserting the freshly compiled kernel and DTB. The output name is `ALice_boot.img`.
- Do not treat a green build as proof of device boot, radio, camera, thermal or Apple compatibility. Keep existing known-good boot and vendor backups.

## Integration policy
Retain main and previous development branches. Unified source CI is enabled on alice-unified. Original firmware must be compared before selecting vendor replacements. Never advertise unverified HAL or fake AWDL support.
