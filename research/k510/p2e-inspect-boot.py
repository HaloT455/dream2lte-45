#!/usr/bin/env python3
"""Alice K510 P2E: read-only inspect of a LOCAL Samsung BOOT partition backup.

No private stock BOOT binary or extracted firmware is ever uploaded to GitHub.
Does not create boot.img, modify an image, extract kernel/ramdisk or flash.
Usage: python3 research/k510/p2e-inspect-boot.py /path/to/V12R5T-original-BOOT.img
"""
import hashlib
import json
import pathlib
import struct
import sys

def inspect(path):
    p=pathlib.Path(path)
    data=p.read_bytes()
    if data[:8] != b"ANDROID!":
        raise ValueError("Not an Android BOOT image")
    if len(data)<4096:
        raise ValueError("BOOT too small")
    vals=struct.unpack_from("<9I",data,8)
    ks,ka,rs,ra,ss,sa,ta,page,dt_size=vals
    if page not in (2048,4096,8192,16384):
        raise ValueError("Invalid page size")
    if not all((ks>0,rs>0,ss==0,dt_size>=2048)):
        raise ValueError("Unsupported boot segment layout")
    align=lambda n:(n+page-1)//page*page
    kernel_off=page
    ramdisk_off=kernel_off+align(ks)
    primary_off=ramdisk_off+align(rs)+align(ss)
    dt_end=primary_off+align(dt_size)
    if dt_end>len(data):
        raise ValueError("DT section exceeds BOOT image")

    def examine_dtbh(off):
        if off+2048+40>len(data) or data[off:off+4]!=b"DTBH":
            raise ValueError("DTBH signature missing")
        fields=struct.unpack_from("<11I",data,off)
        # The DTBH format is Samsung-specific, NOT Android dt_table_header.
        # Interpret only verified common fields, not unknown vendor values.
        version=fields[1];entries=fields[2]
        if not (version==2 and 0<entries<=128):
            raise ValueError("Unexpected DTBH version/count")
        # Measured SM-G955F source uses 2 KiB header and FDT at +0x800.
        fdt_off=off+2048
        if data[fdt_off:fdt_off+4]!=b"\xd0\x0d\xfe\xed":
            raise ValueError("Missing FDT magic inside DTBH")
        totalsize=struct.unpack_from(">I",data,fdt_off+4)[0]
        if not (40<=totalsize<=16*1024*1024):
            raise ValueError("Implausible FDT size")
        return {
            "offset":off,
            "dtbh_version":version,
            "dtbh_entry_count":entries,
            "platform_id":fields[3],
            "fdt_offset":fdt_off,
            "fdt_totalsize":totalsize,
            "fdt_within_declared_dt_size":(fdt_off+totalsize<=off+dt_size)
        }

    primary=examine_dtbh(primary_off)
    # Scan only within BOOT data, and compare full declared DTBH section.
    copies=[]
    scan_start=dt_end
    while True:
        pos=data.find(b"DTBH",scan_start)
        if pos<0 or pos>=len(data)-2048:
            break
        scan_start=pos+4
        if pos+dt_size>len(data):
            continue
        if data[pos:pos+dt_size]==data[primary_off:primary_off+dt_size]:
            try:
                copies.append(examine_dtbh(pos))
            except ValueError:
                pass
        if len(copies)>=8:
            break

    samsung_marker=data.find(b"SEANDROIDENFORCE",dt_end)
    if samsung_marker<0:
        samsung_marker=None
    footer=None
    if data[-64:-60]==b"AVBf":
        major,minor,original,vbmeta_off,vbmeta_size=struct.unpack_from(
            ">IIQQQ",data,len(data)-60)
        plausible=(0<original<=vbmeta_off and
                   vbmeta_off+vbmeta_size<=len(data)-64)
        has_vbmeta=(plausible and data[vbmeta_off:vbmeta_off+4]==b"AVB0")
        footer={
            "marker":"AVBf","major":major,"minor":minor,
            "original_image_size":original,
            "vbmeta_offset":vbmeta_off,
            "vbmeta_size":vbmeta_size,
            "vbmeta_structure_consistent":bool(has_vbmeta),
            "warning":("Footer marker alone does NOT establish a valid "
                       "AVB signature or verified boot status")
        }
    return {
        "label":"K510 P2E read-only stock BOOT structure",
        "partition_bytes":len(data),
        "sha256":hashlib.sha256(data).hexdigest(),
        "android_boot_page_size":page,
        "kernel_size":ks,"kernel_offset":kernel_off,
        "ramdisk_size":rs,"ramdisk_offset":ramdisk_off,
        "legacy_dt_field":dt_size,"primary_dtbh":primary,
        "legacy_declared_section_end":dt_end,
        "extra_matching_dtbh_copies":copies,
        "seandroidenforce_offset":samsung_marker,
        "last64_avb_footer":footer,
        "header_load_addresses_outside_live_ram":True,
        "warning":("Use for offline research ONLY. The loader's DRAM "
                   "handoff and memory relocation are unverified. "
                   "Do NOT flash a repacked image.")
    }

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python3 p2e-inspect-boot.py /path/to/local-BOOT.img")
    print(json.dumps(inspect(sys.argv[1]),indent=2))
