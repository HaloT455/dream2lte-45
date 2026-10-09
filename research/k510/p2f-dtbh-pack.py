#!/usr/bin/env python3
"""P2F: Samsung DTBH v2 builder, one compiler-test SM-G955F entry.
Creates a DTBH container only. Never creates a boot.img or signs firmware.
"""
import argparse
import pathlib
import struct

PAGE=2048
CHIP=8895
PLATFORM=0x000050a6
SUBTYPE=0x217584da
HW_REV=10
HW_REV_END=255

def align(n):
    return (n+PAGE-1)//PAGE*PAGE

def package(blob):
    if len(blob)<40 or blob[:4]!=b'\xd0\x0d\xfe\xed':
        raise ValueError('Not a flattened device tree')
    totalsize=struct.unpack_from('>I',blob,4)[0]
    if totalsize!=len(blob):
        raise ValueError('FDT totalsize differs from actual byte length')
    if len(blob)>8*1024*1024:
        raise ValueError('Unexpectedly large Device Tree')
    if b'samsung,dream2lte\0' not in blob:
        raise ValueError('Not a Samsung dream2lte Device Tree')
    if b'SM-G955F' not in blob:
        raise ValueError('SM-G955F board marker missing')
    padded=align(len(blob))
    header=bytearray(PAGE)
    struct.pack_into('<4s10I',header,0,b'DTBH',2,1,CHIP,PLATFORM,SUBTYPE,HW_REV,HW_REV_END,PAGE,padded,0x20)
    return bytes(header)+blob+bytes(padded-len(blob))

def main():
    ap=argparse.ArgumentParser(description='SM-G955F rev05 CI-only DTBH packer, NOT FLASHABLE')
    ap.add_argument('dtb',type=pathlib.Path)
    ap.add_argument('output',type=pathlib.Path)
    args=ap.parse_args()
    src=args.dtb.read_bytes()
    output=package(src)
    if args.dtb.resolve()==args.output.resolve():
        raise SystemExit('Refusing to overwrite source DTB')
    args.output.write_bytes(output)
    print(f'SM-G955F DTBH v2: entry=1 chip={CHIP} hw_rev={HW_REV}-{HW_REV_END} size={len(output)}')
    print('Compiler proof only. Not verified for S-Boot. DO NOT FLASH.')

if __name__=='__main__':
    main()
