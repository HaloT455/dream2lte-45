# Alice K510 P2E – full stock BOOT structure: sanitized audit

**Device**: Samsung Galaxy S8+ SM-G955F rev05 (Exynos 8895)
**Evidence**: User's read-only 40 MiB BOOT backup captured 2026-10-10 at 05:34 (+07). The raw binary is **not** committed.

- BOOT partition size: **41,943,040 bytes**
- SHA-256: `76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823`
- Legacy `ANDROID!` image, 2048-byte page size.
- Kernel raw ARM64 Image at offset **2,048** (kernel size **38,149,864**; `ARMd` header signature).
- Gzip ramdisk at offset **38,152,192** (size **700,389**).
- Primary Samsung `DTBH` v2 at offset **38,852,608** (advertised dt size **229,376**).
- Primary Samsung `DTBH` reports version 2, one entry, Exynos platform ID **8895**, and embeds FDT at `+2048` (FDT totalsize **227,317**; DTBH declares **227,328**). Its FDT contains `SM-G955F rev05`.
- **Second byte-for-byte identical DTBH section** at offset **39,106,560**. The second section starts **24,576 bytes** after the primary declared DT section end (39,081,984). It is *outside the normal Android legacy DT size accounted for by the header*.
- Samsung `SEANDROIDENFORCE` text at offset **39,335,936**.
- A `AVBf`-looking marker occurs at final 64 bytes of the 40 MiB partition: offset **41,942,976**. Parsed as big-endian footer v1.0 its original image size is **33,216,528**, vbmeta offset **33,218,560**, vbmeta size **2,112**. The purported vbmeta location is **inside the current kernel section** and **does not begin with `AVB0`**. Thus this footer is structurally inconsistent with the *current* BOOT layout. It could be an orphaned residue from a prior flash, but that hypothesis is unproven. **Never claim it is a valid AVB footer or preserve it blindly.**
- Header load addresses `0x10008000` (kernel), `0x11000000` (ramdisk), `0x10000100` (tags) remain outside the actual P1D live-Device-Tree RAM ranges. Do not infer Linux 5.10 load addresses from those header fields without S-Boot/uniLoader relocation evidence.
- The raw backup includes private installed-image content; keep offline. No modem/EFS/userdata partitions were backed up.

## Gate status

- **P1E CI cross-build** passed.
- **P2A CI** cross-built Linux 5.10 ARM64 Image, Device Tree, initramfs, and S8 donor uniLoader (not hardware-boot validated).
- **P2B CI** compiled dedicated SM-G955F uniLoader board target (unverified actual board handoff).
- **P2C** validates boot header metadata, not Samsung vendor appended data; P2E establishes the additional sections observed above.
- **P2E parser** `p2e-inspect-boot.py` can inspect the private backup locally. CI tests this code with synthetic fixtures; the private BOOT image is intentionally never uploaded to public GitHub Actions.

### Critical follow-up

1. Implement a Samsung `DTBH`-aware image structure tool and separately verify the origin/role of the **duplicate DTBH** section.
2. Investigate `SEANDROIDENFORCE` and footer conventions, including validated original image end and any AVB/vbmeta signature expectations. No signing bypass is proposed.
3. Determine real S-Boot memory relocation and loader physical addresses for SM-G955F rev05; validate reserved-memory safety.
4. Port actual UFS/PMIC/early console support; then prepare an early-boot **hardware test** with confirmed restore route.
5. A boot image must be treated as experimental and cannot be released as flashable based on current compiler passes.

**P2E is structural research only, NOT a flashable 5.10 boot.img.**
