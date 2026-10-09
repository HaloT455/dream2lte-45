#!/usr/bin/env bash
# P2A: inspect ONLY the first 4 KiB of the known-good Android BOOT partition.
# Read-only. Does not write block devices, recovery, or boot image.
set -euo pipefail
command -v adb >/dev/null
[[ "$(adb devices | awk '$2=="device" {n++} END {print n+0}')" == 1 ]] || {
  echo "Expected exactly one connected ADB device" >&2; exit 2;
}
HW="$(adb shell getprop ro.hardware | tr -d '\r')"
[[ "$HW" == samsungexynos8895 ]] || {
  echo "Unexpected hardware: $HW" >&2; exit 3;
}
adb shell "su -c 'id'" | grep -q 'uid=0' || {
  echo "KernelSU root required" >&2; exit 4;
}
OUTDIR="$HOME/V12R5T_TEST"
mkdir -p "$OUTDIR"
HEADER="$(mktemp)"
trap 'rm -f "$HEADER"' EXIT
# Samsung S8+ BOOT is /dev/block/sda7, confirmed by live partition symlinks.
# Use stable by-name symlink and READ ONLY dd; never point this to a write command.
adb exec-out "su -c 'dd if=/dev/block/by-name/BOOT bs=4096 count=1 2>/dev/null'" > "$HEADER"
OUT="$OUTDIR/k510-p2-boot-header-$(date +%Y%m%d-%H%M%S).txt"
python3 - "$HEADER" "$OUT" <<'PY'
import pathlib,struct,sys
p=pathlib.Path(sys.argv[1]); raw=p.read_bytes()
lines=["Alice K510 P2 read-only boot-header analysis",
       "Device verified by ro.hardware=samsungexynos8895",
       "Partition source: /dev/block/by-name/BOOT (READ ONLY)",
       f"Header bytes returned: {len(raw)}"]
if len(raw)<4096:
    lines.append("ERROR: header shorter than one 4096-byte block")
elif raw[:8]!=b"ANDROID!":
    lines.append("Not a recognized Android boot.img ANDROID! header")
    lines.append("No fields were interpreted; do not guess packing format.")
else:
    fields=["kernel_size","kernel_addr","ramdisk_size","ramdisk_addr",
            "second_size","second_addr","tags_addr","page_size",
            "dt_size_or_header_version"]
    values=struct.unpack_from("<9I",raw,8)
    for name,v in zip(fields,values):
        if name.endswith("size") or name=="page_size" or name=="dt_size_or_header_version":
            lines.append(f"{name}: {v} (0x{v:x})")
        else:
            lines.append(f"{name}: 0x{v:08x}")
    name=raw[48:64].split(b"\0")[0].decode("ascii","replace")
    lines.append(f"boot_image_name: {name!r}")
    lines.append("NOTICE: offset 0x28 is dt_size on legacy v0 layouts; boot header")
    lines.append("versions must be confirmed before interpreting dt_size.")
    lines.append("NOTICE: cmdline and image ID intentionally withheld.")
lines.append("No phone partitions changed.")
pathlib.Path(sys.argv[2]).write_text("\n".join(lines)+"\n")
print("\n".join(lines))
print("REPORT="+sys.argv[2])
PY
