#!/usr/bin/env python3
"""P2E CI fixture: synthetic Samsung legacy BOOT, never a real user boot image."""
import importlib.util
import pathlib
import struct
import tempfile

here=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("p2e_audit",here/"p2e-inspect-boot.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
page=2048;ks=4096;rs=2048;ds=4096
first=page+ks+rs
second=first+ds+4096
marker=second+ds
total=2*1024*1024
buf=bytearray(total)
buf[0:8]=b"ANDROID!"
struct.pack_into("<9I",buf,8,ks,0x10008000,rs,0x11000000,0,0x10f00000,
                 0x10000100,page,ds)
buf[page+0x38:page+0x3c]=b"ARMd"
buf[page+ks:page+ks+2]=b"\x1f\x8b"
dtbh=bytearray(ds)
struct.pack_into("<11I",dtbh,0,int.from_bytes(b"DTBH","little"),2,1,8895,
                 20646,0,10,255,2048,100,32)
struct.pack_into(">II",dtbh,2048,0xd00dfeed,100)
buf[first:first+ds]=dtbh
buf[second:second+ds]=dtbh
buf[marker:marker+16]=b"SEANDROIDENFORCE"
# Intentionally inconsistent final AVBf marker; vbmeta target has no AVB0.
buf[-64:-60]=b"AVBf"
struct.pack_into(">IIQQQ",buf,len(buf)-60,1,0,12345,16000,128)
with tempfile.TemporaryDirectory() as d:
    img=pathlib.Path(d)/"not-flashable-synthetic.bin"
    img.write_bytes(buf)
    result=mod.inspect(img)
assert result["partition_bytes"]==total
assert result["android_boot_page_size"]==2048
assert result["primary_dtbh"]["dtbh_version"]==2
assert result["primary_dtbh"]["platform_id"]==8895
assert result["primary_dtbh"]["fdt_totalsize"]==100
assert len(result["extra_matching_dtbh_copies"])==1
assert result["extra_matching_dtbh_copies"][0]["offset"]==second
assert result["seandroidenforce_offset"]==marker
assert result["last64_avb_footer"]["vbmeta_structure_consistent"] is False
assert result["header_load_addresses_outside_live_ram"] is True
print("P2E synthetic legacy BOOT/DTBH duplication/invalid AVB footer parser tests PASSED")
print("This test never used a real BOOT image and generated no flashable artifact.")
