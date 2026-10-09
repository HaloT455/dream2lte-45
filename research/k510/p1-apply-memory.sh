#!/usr/bin/env bash
# K510 P1D: produce a compile-only SM-G955F rev05 memory overlay, based on
# measured live DT fields. NEVER use resulting DTB to flash a phone.
set -euo pipefail
TREE="${1:?Usage: bash p1-apply-memory.sh /path/to/linux-5.10.262}"
HERE="$(cd "$(dirname "$0")" && pwd)"
[[ "$(make -s -C "$TREE" kernelversion)" == 5.10.* ]] || {
  echo 'Only Linux 5.10.x source allowed' >&2; exit 2;
}
export P1D_TREE="$TREE" P1D_MANIFEST="$HERE/P1D-RMEM.txt"
python3 - <<'PY'
import os, pathlib, re

tree=pathlib.Path(os.environ["P1D_TREE"])
manifest=pathlib.Path(os.environ["P1D_MANIFEST"])
dts=tree/"arch/arm64/boot/dts/exynos/exynos8895-dream2lte.dts"
if not dts.is_file():
    raise SystemExit("P1A import-dts must run before P1D")
text=dts.read_text()
if "ALICE_P1D_MEMORY_BEGIN" in text:
    raise SystemExit("P1D already applied; refusing double insertion")
if "memory@80000000" in text or "reserved-memory {" in text:
    raise SystemExit("Unexpected prior memory definitions; refusing to overwrite")

mem=[
    ("0x80000000", "0x3c800000"),
    ("0xc0000000", "0x40000000"),
    ("0x880000000", "0x80000000"),
]
reserved=[]
for line in manifest.read_text().splitlines():
    line=line.strip()
    if not line or line.startswith("#"):
        continue
    fields=line.split()
    if len(fields)!=3 or not re.fullmatch(r"[a-z_]+",fields[0]):
        raise SystemExit("Invalid reserved-memory line: "+line)
    name, addr, size=fields
    if not re.fullmatch(r"0x[0-9a-fA-F]+",addr) or not re.fullmatch(r"0x[0-9a-fA-F]+",size):
        raise SystemExit("Invalid hex address/size: "+line)
    reserved.append((name,int(addr,16),int(size,16)))
if len(reserved)!=12:
    raise SystemExit("P1D requires exactly 12 measured reserved-memory ranges")
def fits(a,n):
    return any(a>=int(b,16) and a+n<=int(b,16)+int(sz,16) for b,sz in mem)
ranges=sorted(reserved,key=lambda r:r[1])
for i,(name,addr,size) in enumerate(ranges):
    if size==0 or not fits(addr,size):
        raise SystemExit("Reserved range outside measured RAM: "+name)
    if i and ranges[i-1][1]+ranges[i-1][2]>addr:
        raise SystemExit("Overlapping reservation: "+ranges[i-1][0]+" and "+name)
memreserve_start,memreserve_size=0xe0000000,0x1900000
if not fits(memreserve_start,memreserve_size):
    raise SystemExit("Samsung legacy /memreserve/ outside measured RAM")
if any(a < memreserve_start+memreserve_size and a+n > memreserve_start
       for _,a,n in reserved):
    raise SystemExit("Samsung legacy /memreserve/ conflicts with live DT nodes")
if not re.search(r"(?m)^/dts-v1/;", text):
    raise SystemExit("Unexpected board DTS header")
text=text.replace("/dts-v1/;",
                  "/dts-v1/;\n"
                  "/* Alice P1D: legacy Samsung 4.4 exynos8895-rmem.dtsi; "
                  "not verified from the current log */\n"
                  "/memreserve/ 0xe0000000 0x1900000;",1)

def addr_cells(addr):
    return f"0x{(addr>>32)&0xffffffff:08x} 0x{addr&0xffffffff:08x}"
part=[
  "\n/* ALICE_P1D_MEMORY_BEGIN -- compile-only, NOT flashable */\n",
  "/ {\n",
  "    /* SM-G955F rev05 memory obtained from live /proc/device-tree/reg. */\n",
  "    memory@80000000 {\n",
  "        device_type = \"memory\";\n",
  "        reg =\n"
]
for i,(a,z) in enumerate(mem):
    base=int(a,16);size=int(z,16)
    part.append(f"            <{addr_cells(base)} 0x{size:08x}>"+
                (",\n" if i<len(mem)-1 else ";\n"))
part.extend([
    "    };\n",
    "    reserved-memory {\n",
    "        #address-cells = <2>;\n",
    "        #size-cells = <1>;\n",
    "        ranges;\n",
    "        /* Safety-first isolation: temporarily no-map all live carveouts. */\n"
])
for name,base,size in ranges:
    part.extend([f"        {name}@{base:x} {{\n",
                 f"            reg = <{addr_cells(base)} 0x{size:08x}>;\n",
                 "            no-map;\n",
                 "        };\n"])
part.extend(["    };\n","};\n",
             "/* ALICE_P1D_MEMORY_END -- hardware boot NOT validated */\n"])
dts.write_text(text+"".join(part))
print("P1D: inserted 3 measured RAM regions and 12 conservative no-map carveouts")
print("P1D: added legacy vendor /memreserve/ from Samsung 4.4, independent source")
print("P1D: zero-sized memory@900000000 deliberately excluded")
print("P1D NOT BOOTABLE: hardware bootloader/PMIC/storage/power handoff not validated")
PY
