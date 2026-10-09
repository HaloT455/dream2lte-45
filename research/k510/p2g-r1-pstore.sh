#!/usr/bin/env bash
# P2G-R1: persistent log reservation + Linux 5.10 pstore configs.
# CI/compiler only; does not touch phone partitions.
set -euo pipefail
TREE="$1"
OUT="$2"
test -s "$TREE/arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
test -f "$OUT/.config"
python3 - "$TREE/arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
src=p.read_text()
if 'ALICE_K510_R1_PSTORE' in src:
    raise SystemExit("P2G-R1 already applied")
if 'ALICE_P1D_MEMORY_BEGIN' not in src or 'ALICE_K510_P2_CHOSEN' not in src:
    raise SystemExit("Missing measured P1D memory or P2 chosen data")
src += """
/* ALICE_K510_R1_PSTORE: TWRP 4.4 observation, hardware boot unverified */
&{/reserved-memory} {
    k510_ramoops: ramoops@92000000 {
        compatible = "ramoops";
        reg = <0x00000000 0x92000000 0x00008000>;
        record-size = <0x00004000>;
        console-size = <0x00004000>;
        no-map;
    };
};
/* Logs only survive if kernel reaches pstore init and RAM survives reset. */
"""
old='bootargs = "rdinit=/init loglevel=7 printk.time=1";'
new='bootargs = "rdinit=/init loglevel=7 printk.time=1 ignore_loglevel printk.always_kmsg_dump=1 initcall_debug";'
if src.count(old)!=1:
    raise SystemExit("Unexpected P2 chosen bootargs")
p.write_text(src.replace(old,new,1))
print("P2G-R1: reserved 32 KiB ramoops at 0x92000000")
PY
"$TREE/scripts/config" --file "$OUT/.config" --enable PSTORE \
  --enable PSTORE_CONSOLE --enable PSTORE_PMSG --enable PSTORE_RAM \
  --disable PSTORE_FTRACE
make -s -C "$TREE" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
for key in PSTORE PSTORE_CONSOLE PSTORE_PMSG PSTORE_RAM; do
  grep -q "^CONFIG_$key=y$" "$OUT/.config" || { echo "Not enabled $key"; exit 5; }
done
echo "P2G-R1: pstore configs verified; not a proof of bootability."
