#!/usr/bin/env python3
"""Build an UNSIGNED experimental SM-G955F S-Boot format image.

FOR RESEARCH ONLY; may fail to boot, will not boot Android 16, may bootloop.
No partitions are written by this script. The stock 40MiB BOOT backup remains
private and is not used in this builder.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import struct
import sys

PAGE=2048
PARTITION_SIZE=41943040
BOARD=b"SRPPK02A007KU"
LOAD_KERNEL=0x10008000
LOAD_RAMDISK=0x11000000
LOAD_SECOND=0x10f00000
LOAD_TAGS=0x10000100
MARKER=b"SEANDROIDENFORCE"

def pad(n: int) -> int:
    return (n+PAGE-1)//PAGE*PAGE

def read_checked(path: pathlib.Path) -> bytes:
    data=path.read_bytes()
    if not data:
        raise ValueError(f"Empty payload: {path}")
    return data

def build(loader: bytes, ramdisk: bytes, dtbh: bytes) -> tuple[bytes, dict]:
    # Strictly validate generated Samsung DTBH table. Never accept a generic FDT.
    if len(dtbh)<PAGE+40 or dtbh[:4]!=b"DTBH":
        raise ValueError("Invalid Exynos DTBH magic or length")
    table=struct.unpack_from("<4s10I",dtbh)
    _,version,entries,chip,platform,subtype,rev,rev_end,offset,length,space=table
    if (version,entries,chip,platform,subtype,rev,rev_end,offset,space) != (
            2,1,8895,0x50a6,0x217584da,10,255,2048,32):
        raise ValueError("Unexpected Exynos8895 DTBH hardware entry")
    if len(dtbh)!=offset+length or length%PAGE:
        raise ValueError("Invalid padded DTBH length")
    if dtbh[offset:offset+4]!=b"\xd0\x0d\xfe\xed":
        raise ValueError("Missing embedded FDT")
    fdt_size=struct.unpack_from(">I",dtbh,offset+4)[0]
    if fdt_size<40 or fdt_size>length:
        raise ValueError("Invalid embedded FDT size")
    if b"samsung,dream2lte\x00" not in dtbh and b"SM-G955F" not in dtbh:
        raise ValueError("Not SM-G955F device tree")
    if len(loader)>60000000 or len(ramdisk)>8000000:
        raise ValueError("Implausible payload size")
    if not ramdisk[:2]==b"\x1f\x8b":
        raise ValueError("Expected gzip initramfs")

    head=bytearray(PAGE)
    struct.pack_into("<8s10I",head,0,b"ANDROID!",len(loader),LOAD_KERNEL,
                     len(ramdisk),LOAD_RAMDISK,0,LOAD_SECOND,LOAD_TAGS,
                     PAGE,len(dtbh),0)
    head[48:48+len(BOARD)]=BOARD
    cmdline=b"rdinit=/init loglevel=7 printk.time=1"
    head[64:64+len(cmdline)]=cmdline
    # Legacy Android SHA1 ID including Samsung DT block.
    hash=hashlib.sha1()
    for blob in (loader,ramdisk,b""):
        hash.update(blob)
        hash.update(struct.pack("<I",len(blob)))
    hash.update(dtbh)
    hash.update(struct.pack("<I",len(dtbh)))
    head[576:596]=hash.digest()
    # No duplicated, unverified DTBH or stale AVB footer from stock BOOT.
    out=bytearray(head)
    for blob in (loader,ramdisk,dtbh):
        out+=blob
        out+=bytes(pad(len(blob))-len(blob))
    section_end=len(out)
    out+=MARKER
    if len(out)>PARTITION_SIZE:
        raise ValueError(f"BOOT exceeds partition ({len(out)}>{PARTITION_SIZE})")
    out+=bytes(PARTITION_SIZE-len(out))
    meta={
        "target":"SM-G955F rev05 Exynos8895", "status":"EXPERIMENTAL-NOT-BOOT-VALIDATED",
        "kernel_label":"uniLoader embedding genuine Linux 5.10.262, not Android boot kernel",
        "page_size":PAGE,"partition_size":PARTITION_SIZE,
        "boot_image_bytes":len(out),"loader_bytes":len(loader),
        "ramdisk_bytes":len(ramdisk),"dtbh_bytes":len(dtbh),
        "board":BOARD.decode(),"logical_sections_end":section_end,
        "marker_offset":section_end,"contains_legacy_samsung_dtbh":True,
        "duplicate_dtbh_in_stock_intentionally_not_copied":True,
        "signed_or_verified":False,
        "sha256":hashlib.sha256(out).hexdigest(),
        "warning":"BOOTLOOP EXPECTED; NO hardware boot proof; NO AVB signature. "
                  "ONLY attempt with confirmed Download Mode/stock BOOT recovery."
    }
    return bytes(out),meta

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--loader",type=pathlib.Path,required=True)
    ap.add_argument("--ramdisk",type=pathlib.Path,required=True)
    ap.add_argument("--dtbh",type=pathlib.Path,required=True)
    ap.add_argument("--out",type=pathlib.Path,required=True)
    ap.add_argument("--report",type=pathlib.Path,required=True)
    ns=ap.parse_args()
    loader,ramdisk,dtbh=map(read_checked,(ns.loader,ns.ramdisk,ns.dtbh))
    out,meta=build(loader,ramdisk,dtbh)
    if ns.out.resolve() in [ns.loader.resolve(),ns.ramdisk.resolve(),ns.dtbh.resolve()]:
        raise ValueError("Refusing to overwrite any source")
    ns.out.write_bytes(out)
    ns.report.write_text(json.dumps(meta,indent=2)+"\n")
    print(json.dumps(meta,indent=2))
    print("P2G RESEARCH BOOT IMAGE GENERATED. NOT VERIFIED TO BOOT.")

if __name__=="__main__":
    main()
