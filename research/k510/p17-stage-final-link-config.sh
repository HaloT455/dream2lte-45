#!/usr/bin/env bash
# P17 ONLY: enable ACPM/PMIC built-in in disposable Linux 5.10.262 tree,
# test FINAL vmlinux link. NO device probes, boot packaging or flashing.
set -euo pipefail
TREE="$1"; OUT="$2"
test -s "$OUT/.config"
test -s "$TREE/drivers/soc/samsung/Kconfig"
test -s "$TREE/drivers/soc/samsung/acpm/Makefile"
test -s "$TREE/arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
for src in \
  drivers/soc/samsung/acpm/acpm.c \
  drivers/soc/samsung/acpm/acpm_ipc.c \
  drivers/soc/samsung/acpm/acpm_mfd.c \
  drivers/mfd/s2mps17_core.c \
  drivers/mfd/s2mps17_irq.c \
  drivers/regulator/s2mps17.c \
  drivers/regulator/s2mps17_powermeter.c; do
  test -s "$TREE/$src"
done

python3 - "$TREE" <<'PY'
from pathlib import Path
import re,sys
tree=Path(sys.argv[1])
dts=tree/"arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
text=dts.read_text()
node=re.search(r'alice_ufs_embd:\s*ufs@11120000\s*\{(.*?)\n\s*\};',text,re.S)
if not node or not re.search(r'status\s*=\s*"disabled"\s*;',node.group(1)):
    raise SystemExit("P17 REFUSED: experimental UFS must remain disabled")
# P14+P16 require built-in Kbuild objects. Do not let compiler-only flags
# mask missing CONFIG integration.
rules={
    "drivers/soc/samsung/Makefile": ("obj-y += acpm/",),
    "drivers/soc/samsung/acpm/Makefile": (
        "obj-y += acpm.o", "obj-y += acpm_ipc.o", "obj-y += acpm_mfd.o"
    ),
    "drivers/mfd/Makefile": (
        "obj-y += s2mps17_core.o", "obj-y += s2mps17_irq.o"
    ),
    "drivers/regulator/Makefile": ("obj-y += s2mps17.o","obj-y += s2mps17_powermeter.o",),
}
for path,expected in rules.items():
    body=(tree/path).read_text()
    for line in expected:
        if body.splitlines().count(line)!=1:
            raise SystemExit(f"P17 REFUSED: Kbuild rule not unique: {path}:{line}")
kcfg=tree/"drivers/soc/samsung/Kconfig"
s=kcfg.read_text()
if "config EXYNOS_ACPM" in s:
    raise SystemExit("P17 REFUSED: EXYNOS_ACPM already defined; inspect ownership")
# Intentionally standalone experimental toggle, at end of source.
s+='''

# ALICE K510 P17 CI-ONLY. Built-in ACPM could run initcalls on real hardware.
# Do not ever distribute P17 kernel binary or use this config for flashing.
config EXYNOS_ACPM
    bool "Experimental Exynos8895 ACPM full-vmlinux link gate (NEVER FLASH)"
    depends on ARM64 && ARCH_EXYNOS && SOC_SAMSUNG && I2C && REGULATOR
    default n
    help
      Kernel compilation test only. ACPM power sequencing and vendor firmware
      are unvalidated for Linux 5.10. This option must never be used to boot.
'''
kcfg.write_text(s)
print("P17 checked 7 Kbuild donor objects, added real Kconfig option; UFS stays disabled.")
PY

"$TREE/scripts/config" --file "$OUT/.config" \
  --enable EXYNOS_ACPM \
  --disable EXYNOS_SNAPSHOT \
  --disable EXYNOS_SNAPSHOT_ACPM \
  --disable ACPM_DVFS \
  --set-str LOCALVERSION "-ALICE-K510-P17-NOFLASH"
make -s -C "$TREE" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
grep -qx 'CONFIG_EXYNOS_ACPM=y' "$OUT/.config" || {
  echo "P17 config fail: CONFIG_EXYNOS_ACPM=y unresolved dependencies" >&2
  grep -E 'CONFIG_(ARCH_EXYNOS|SOC_SAMSUNG|I2C|REGULATOR|EXYNOS_ACPM)=' "$OUT/.config" >&2 || true
  exit 23
}
grep -qx 'CONFIG_LOCALVERSION="-ALICE-K510-P17-NOFLASH"' "$OUT/.config"
echo 'P17 GATE: genuine CONFIG_EXYNOS_ACPM=y; 7 Kbuild objects included for final vmlinux link.'
echo 'NO FLASH: initcall probe safety not established; no Android init, PMIC, or UFS support validated.'
