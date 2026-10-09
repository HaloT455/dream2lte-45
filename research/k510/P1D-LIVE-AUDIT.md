# P1D read-only Galaxy S8+ DT audit

Device: SM-G955F rev05; memory layout recovered from the phone's running Device Tree. The earlier S8 (SM-G950F) memory configuration must not be assumed applicable. This is not a flashable boot image.

RAM: 0x80000000+0x3c800000, 0xc0000000+0x40000000, 0x880000000+0x80000000. The zero-size entry 0x900000000 is excluded.

The exact reserved-memory entries require an audited compatibility layer, and kernel 5.10 needs successful early boot driver validation before creating a boot image.
