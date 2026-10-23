# ALICE R16 / Vendor A16 SIM2 LTE A/B source pairing — 2026-10-23

**Kernel branch:** `agent/v12r69-r16-sim2-lte-ab-20261023`.
**Vendor branch:** `HaloT455/Vendor-45-/work/a16-sim2-lte-ab-20261023`.

## Reviewed against the owner's SIM-working boot
The owner's `boot.img` is Exynos8895/SM-G955F Linux 4.4.302, compiled with interactive + DH2/HMP policies, not newer R16 EnergyStep. The IKCONFIG's Exynos8895 SIPC/SS310AP/UMTS/SHMEM/NAPI/QoS modem options match R16. No evidence that changing the kernel modem driver can create a second LTE-active baseband/RF path.

## Changes and artifacts
- `scripts/guard_boot_vendor_pair.py`: CI now **rejects** a vendor trying to overwrite Android16's early `ro.telephony.default_network=9,9` via late immutable single-slot `setprop`. It ensures both Samsung NetworkConfig and SimConfig are preserved.
- `scripts/repack_boot_v0.py` on this branch inherits the guard against packaging an old interactive/DH2 ramdisk with R16 EnergyStep.
- Workflow `.github/workflows/alice-v12r69-baseline-build.yml`: pinned Vendor A/B source; includes readable JSON compatibility report and independent SIM2 LTE diagnostic script in its R16 build artifact.
- No kernel driver, CP, NV/EFS or vendor Camera HAL binary is modified in this branch. This is a safe **compatibility build**, not a claimed dual-LTE firmware fix.
- Kernel CI only exports `Image` and `dtb.img`; a R16-compatible base boot image must be verified before assembling a flashable `boot.img`.

## Hard engineering limit
One Exynos8895 LTE RF/CP path is documented for this family. Vendor `ro.telephony.default_network=9,9`, two RIL HIDL endpoints and both SIM cards inserted do not prove 4G+4G. Android16 PhoneSwitcher/RadioConfig may allow transferring LTE ownership from SIM1 to SIM2, but physical proof requires per-slot WWAN LTE service registration. Preserve original working boot, vendor and camera and do not deploy blind dual-LTE workarounds.
