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
- Vendor base is vendor.new.dat.br + vendor.transfer.list. Donor is vendor-a16-sim2-lte-ril-ab-video6-UNTESTED.img. Original binary files cannot be opened in the current processing environment. No real radio/SIM2/LTE/LED/media patches have been applied. Synthetic test is not vendor firmware. See alice/vendor/README.md.
- No proprietary vendor or boot binaries uploaded to the public repository. No flashable vendor.img produced.
- Do not treat a green build as proof of device boot, radio, camera, thermal or Apple compatibility. Keep existing known-good boot and vendor backups.

## Integration policy
Retain main and previous development branches. Unified source CI is enabled on alice-unified. Original firmware must be compared before selecting vendor replacements. Never advertise unverified HAL or fake AWDL support.
