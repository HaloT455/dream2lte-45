#!/usr/bin/env python3
"""P2F read-only SM-G955F stock BOOT DTBH roundtrip.
Runs on user's laptop ONLY. Does not upload, modify, sign or flash any image.
"""
import importlib.util
import pathlib
import struct
import sys

if len(sys.argv)!=2:
    raise SystemExit("Usage: python3 p2f-verify-stock-local.py /path/to/original-BOOT.img")
p=pathlib.Path(sys.argv[1])
data=p.read_bytes()
if data[:8]!=b"ANDROID!":
    raise SystemExit("Wrong Android BOOT image magic")
ks,ka,rs,ra,ss,sa,ta,page,ds=struct.unpack_from("<9I",data,8)
if page!=2048 or ss!=0 or ds==0:
    raise SystemExit("Unsupported stock BOOT geometry")
align=lambda n:(n+page-1)//page*page
start=page+align(ks)+align(rs)
end=start+ds
if end>len(data):
    raise SystemExit("DTBH segment extends beyond BOOT")
primary=data[start:end]
values=struct.unpack_from("<4s10I",primary)
m,version,count,chip,platform,subtype,rev,rev_end,dtb_offset,dtb_size,space=values
assert (m,version,count,chip,platform,subtype,rev,rev_end,dtb_offset,space)==(
    b"DTBH",2,1,8895,0x50a6,0x217584da,10,255,2048,32)
fdt_start=start+dtb_offset
assert data[fdt_start:fdt_start+4]==b"\xd0\x0d\xfe\xed"
fdt_size=struct.unpack_from(">I",data,fdt_start+4)[0]
fdt=data[fdt_start:fdt_start+fdt_size]
if len(fdt)!=fdt_size:
    raise SystemExit("Truncated FDT")
spec=importlib.util.spec_from_file_location(
    "dtbh_packer",pathlib.Path(__file__).with_name("p2f-dtbh-pack.py"))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rebuilt=module.package(fdt)
if rebuilt!=primary:
    raise SystemExit("FAIL: primary Samsung DTBH does not roundtrip")
second=data.find(b"DTBH",end)
matching_second=(second>=0 and data[second:second+ds]==primary)
print("PASS: original primary DTBH rebuilt byte-for-byte without modifying image")
print(f"Device: Exynos8895 SM-G955F rev05")
print(f"DTBH v2 size: {len(primary)} bytes; FDT: {len(fdt)} bytes")
print(f"Primary offset: {start}; identical second: {second if matching_second else 'none'}")
print("Warning: DTBH equivalence DOES NOT prove boot image signature,")
print("        Samsung S-Boot relocation, or Linux 5.10 hardware compatibility.")
print("No private BOOT file was uploaded. No phone partitions were written.")
