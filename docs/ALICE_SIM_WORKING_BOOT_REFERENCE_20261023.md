# ALICE S8+ SIM-working boot reference — comparison with R16 (2026-10-23)

Owner reports that the uploaded `boot.img` and `vendor.new.dat.br` pair permits normal SIM operation on Galaxy S8+ SM-G955F. This report concerns **that specific pair**; it is not a verification of a newly built R16 kernel.

## Reference boot (read-only unpack and SHA-256)

- Boot image SHA-256: `9012313ab3d8b2e15fe00871da4872d4d09f7068211b36604eede6fe138c646b`
- Standard Android boot header, `androidboot.hardware=samsungexynos8895 hlong.device=dream2lte`
- Kernel payload: 32,283,960 bytes, SHA-256 `5f3afc4fad30f6e077b8103eb6ac52e602fcba1ef6ef5f2111441bd5b5ebd97d`
- Ramdisk payload (gzip): 699,524 bytes, SHA-256 `69c8d2fc61295cc7fb3b14901709516f0289e521d6a542a93ecdfe3c09165dcb`
- DT image: 229,376 bytes, SHA-256 `ad861356479173627635f65a80b23b04697f8dcca509f1377804a1ec10eaf818`
- Kernel embedded release: `Linux version 4.4.302`, Android Clang 11; embedded build date 2026-06-01.
- Ramdisk inspected: the outer `init.rc` and two DH2 startup scripts did **not** contain `ro.telephony.default_network`, RIL/DSDS overrides or modem configuration. This does not rule out modem-specific behavior elsewhere in the kernel or framework.

## Comparison with the development tree

The base branch `agent/v12r69-r3-ci-kernel` is the later R16 EnergyStep/PowerHAL kernel source. It is a different compiled kernel from the owner-supplied working image. The working boot image is **not** an alternative R16 artifact.

The paired reference vendor radio init is **byte-identical** to the GitHub Test7 original, but differs from the latest camera/Video6 vendor branch in its handling of late `ro.telephony.default_network`. The isolated vendor A/B branch is:
`HaloT455/Vendor-45-` / `work/a16-sim-reference-boot-vendor-20261023`.

## Safe scope

**No kernel Image, DTB, ramdisk, modem drivers, boot image or source configuration are altered by this branch.** Static checks alone cannot determine whether the observed SIM behavior depends on R16, CP firmware, Android 16 telephony framework, carrier state or a specific vendor property.

To resolve causality, compare per-slot service state with the working boot/vendor pair and then with the newer kernel/vendor using a proven TWRP rollback path. Do not replace radio drivers by binary transplantation or modify EFS, NV, IMEI and modem calibration. Do not claim two concurrent LTE registrations without direct per-slot network evidence.
