#!/usr/bin/env python3
"""P25/P26 offline boot-test readiness audit. READ ONLY / NO PACK / NO FLASH.

SM-G955F Exynos8895: kernel compilation is not proof of UFS enumeration
or S-Boot/uniLoader -> Linux handoff. Explicitly separate an experimental
debug-boot assembly gate from Android boot eligibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ORIGINAL_BOOT_BYTES = 41943040
ORIGINAL_BOOT_SHA256 = (
    "76ab5c78bb475eba5fb994bd7a6269c693a652e6698eb68fbd9f5c858c176823"
)

def status(path: Path) -> dict:
    return {"file": path.name, "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else 0}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def audit(folder: Path) -> dict:
    blockers: list[str] = []
    files = ["V12R5T-BOOT.img", "K510-Image",
             "K510-dream2lte.dtb", "K510-uniloader.bin",
             "K510-debug-initramfs.gz",
             "SBOOT-UNILOADER-HANDOFF-OBSERVED.txt",
             "LINUX510-EARLY-BOOT-OBSERVED.txt",
             "UFS510-READONLY-ENUMERATION-OBSERVED.txt",
             "ACPM-S2MPS17-POWER-VALIDATED.txt",
             "SMC-FMP-ABI-VALIDATED.txt",
             "V12R5T-BOOT-ROLLBACK-VERIFIED.txt"]
    present = {key: status(folder / key) for key in files}
    boot = folder / "V12R5T-BOOT.img"
    original_boot_verified = (
        boot.is_file() and boot.stat().st_size == ORIGINAL_BOOT_BYTES
        and sha256_file(boot) == ORIGINAL_BOOT_SHA256
    )
    if not original_boot_verified:
        blockers.append(
            "Missing/mismatched original V12R5T BOOT 40MiB rollback copy "
            "(exact original SHA256 required)."
        )
    if not (folder / "K510-Image").is_file():
        blockers.append("No kernel Image from the exact P24/P25 Linux 5.10.262 CI source revision.")
    if not (folder / "K510-dream2lte.dtb").is_file():
        blockers.append("No exact matching SM-G955F rev05 Device Tree.")
    if not (folder / "K510-uniloader.bin").is_file():
        blockers.append("No audited and instrumented uniLoader with verified memory handoff.")
    if not (folder / "K510-debug-initramfs.gz").is_file():
        blockers.append("No debug-only initramfs for early-boot evidence.")

    # Trust levels: files existing does not prove logs came from actual
    # hardware or their claims are true. A human must authenticate origin.
    handoff = (folder / "SBOOT-UNILOADER-HANDOFF-OBSERVED.txt").is_file()
    early = (folder / "LINUX510-EARLY-BOOT-OBSERVED.txt").is_file()
    storage = (folder / "UFS510-READONLY-ENUMERATION-OBSERVED.txt").is_file()
    power = (folder / "ACPM-S2MPS17-POWER-VALIDATED.txt").is_file()
    smc = (folder / "SMC-FMP-ABI-VALIDATED.txt").is_file()
    restore = (folder / "V12R5T-BOOT-ROLLBACK-VERIFIED.txt").is_file()
    if not handoff:
        blockers.append("No genuine pre-Linux uniLoader stage/handoff evidence (R1/R2 hung on splash).")
    if not early:
        blockers.append("No verified Linux 5.10 early printk, pstore, or PID1 runtime log.")
    if not restore:
        blockers.append("No device-proven BOOT-only restore and recovery method documented.")
    if not storage:
        blockers.append("Exynos8895 UFS has not enumerated read-only under Linux 5.10.")
    if not power:
        blockers.append("Exynos8895 GPIO UFS VCC and ACPM/Speedy/S2MPS17 power runtime unverified.")
    if not smc:
        blockers.append("Samsung secure-monitor FMP/SMU ABI and encryption state runtime unverified.")

    # Even complete disk evidence needs an independent review; this program
    # never generates a boot image or authorizes user flash.
    return {
        "target": "Samsung Galaxy S8+ SM-G955F Exynos8895",
        "audit": "compile artifact versus actual hardware boot eligibility",
        "original_boot_expected_sha256": ORIGINAL_BOOT_SHA256,
        "original_boot_verified": original_boot_verified,
        "source_files": present,
        "prelinux_handoff_observed": handoff,
        "linux_510_entry_observed": early,
        "ufs510_read_only_enumeration_observed": storage,
        "acpm_pmic_runtime_verified": power,
        "smc_fmp_runtime_verified": smc,
        "boot_only_restore_evidence_present": restore,
        "diagnostic_boot_ready_to_flash": False,
        "android16_boot_ready_to_flash": False,
        "why_not_ready": blockers + [
            "No on-device review of source authenticity, signing/DTBH/AVB, "
            "hardware debug capture, or Samsung S-Boot memory ownership. "
            "This tool NEVER approves flashing."
        ],
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit(args.evidence_dir)
    output = json.dumps(report, indent=2) + "\n"
    print(output, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output)
    print("P26 BOOT PACK/FLASH GATE: REFUSED — hardware/boot chain not verified")
    return 3

if __name__ == "__main__":
    raise SystemExit(main())
