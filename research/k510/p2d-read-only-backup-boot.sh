#!/usr/bin/env bash
# P2D: READ ONLY backup of the *currently working* Galaxy S8+ BOOT partition.
# Emits structural report without private Android command line or IDs.
# Never writes any partition. Preserve the backed-up image on your own disk.
set -euo pipefail
command -v adb >/dev/null || { echo 'adb is required' >&2; exit 2; }
[[ "$(adb devices | awk '$2=="device" {n++} END{print n+0}')" == 1 ]] || {
  echo 'Exactly one authorized Android device is required' >&2; exit 3;
}
ROOT="$(adb shell 'su -c id' | tr -d '\r')"
[[ "$ROOT" == *"uid=0"* ]] || { echo 'KernelSU root required' >&2; exit 4; }
HW="$(adb shell getprop ro.hardware | tr -d '\r')"
[[ "$HW" == samsungexynos8895 ]] || {
  echo "Incorrect SoC: $HW" >&2; exit 5;
}
MODEL="$(adb shell "su -c 'cat /proc/device-tree/model'" | tr -d '\000\r')"
[[ "$MODEL" == *"SM-G955F"* ]] || { echo "Not SM-G955F: $MODEL" >&2; exit 6; }
SIZE="$(adb shell "su -c 'blockdev --getsize64 /dev/block/by-name/BOOT'" | tr -d '\r')"
[[ "$SIZE" =~ ^[0-9]+$ ]] || { echo 'Could not verify BOOT partition size' >&2; exit 7; }
[[ "$SIZE" -ge 39081984 && "$SIZE" -le 268435456 ]] || {
  echo "Unexpected BOOT partition size: $SIZE" >&2; exit 8;
}
OUTDIR="$HOME/V12R5T_TEST/K510_P2D"
mkdir -p "$OUTDIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
IMG="$OUTDIR/V12R5T-original-BOOT-$STAMP.img"
REPORT="$OUTDIR/P2D-boot-structure-$STAMP.txt"
echo "Reading BOOT partition ($SIZE bytes) to local backup (no device writes)..."
adb exec-out "su -c 'dd if=/dev/block/by-name/BOOT bs=1048576 2>/dev/null'" > "$IMG"
LOCAL_SIZE="$(stat -c %s "$IMG")"
[[ "$LOCAL_SIZE" == "$SIZE" ]] || {
  echo "Incomplete backup: $LOCAL_SIZE instead of $SIZE bytes" >&2; exit 9;
}
python3 - "$IMG" "$REPORT" <<'PY'
from pathlib import Path
import struct,hashlib,sys

img=Path(sys.argv[1])
size=img.stat().st_size
with img.open("rb") as fh:
    header=fh.read(4096)
assert header[:8] == b"ANDROID!", "BOOT is not an Android legacy boot header"
values=struct.unpack_from("<10I", header, 8)
(k_size,k_addr,r_size,r_addr,s_size,s_addr,t_addr,page,dt_field,unused)=values
assert page in (2048,4096,8192,16384), "Unexpected boot image page"
assert k_size>0 and r_size>0 and s_size==0, "Unexpected segment sizes"
assert dt_field>=2048 and dt_field%4==0, "Legacy dt_size assumption not proven"
def align(n):
    return (n+page-1)//page*page
offset_kernel=page
offset_ramdisk=offset_kernel+align(k_size)
offset_dt=offset_ramdisk+align(r_size)+align(s_size)
expected_end=offset_dt+align(dt_field)
assert expected_end<=size, "The assumed legacy image sections exceed BOOT partition"
with img.open("rb") as fh:
    fh.seek(offset_dt)
    prefix=fh.read(16)
with img.open("rb") as fh:
    digest=hashlib.file_digest(fh,"sha256").hexdigest()
report=[
    "Alice K510 P2D – full-stock-BOOT structural inspection (READ ONLY)",
    "Hardware: SM-G955F / Exynos8895",
    "Image magic: ANDROID!",
    f"Partition bytes: {size}",
    f"Current BOOT SHA256: {digest}",
    f"Page size: {page}",
    f"Kernel size: {k_size}",
    f"Kernel header addr: 0x{k_addr:08x}",
    f"Ramdisk size: {r_size}",
    f"Ramdisk header addr: 0x{r_addr:08x}",
    f"Second size: {s_size}",
    f"Tags header addr: 0x{t_addr:08x}",
    f"Legacy dt_size hypothesis: {dt_field}",
    f"Kernel offset: {offset_kernel}",
    f"Ramdisk offset: {offset_ramdisk}",
    f"DT offset: {offset_dt}",
    f"DT first 16 bytes (hex): {prefix.hex(' ')}",
    f"Minimum image section end: {expected_end}",
    f"Tail bytes in BOOT partition: {size-expected_end}",
    "IMPORTANT: No verification yet of Samsung-specific signatures or loader relocation.",
    "No cmdline, boot image name or image ID is included in this report.",
    "No partitions were written. Keep local backup private and safe.",
]
Path(sys.argv[2]).write_text("\n".join(report)+"\n")
print("\n".join(report))
print("REPORT="+sys.argv[2])
PY
echo "BACKUP STORED LOCALLY: $IMG"
echo 'Only share the small text report; KEEP THE BOOT .img ON YOUR LAPTOP.'
