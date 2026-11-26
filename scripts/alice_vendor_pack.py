#!/usr/bin/env python3
"""Full block OTA (not incremental); byte-for-byte round-trip check."""
import pathlib as P
import subprocess as S
import sys
import tempfile
from alice_vendor_merge import B, digest, unpack, fscheck

def main():
    image=P.Path(sys.argv[1]).resolve()
    out=P.Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    if image.stat().st_size % B: raise ValueError('image not aligned')
    fscheck(image)
    blocks=image.stat().st_size//B
    if not 0<blocks<=1000000: raise ValueError('invalid image size')
    tl=out/'vendor.transfer.list'
    with tl.open('w') as f:
        f.write(f'4\n{blocks}\n0\n0\n')
        for start in range(0,blocks,1024):
            f.write(f'new 2,{start},{min(start+1024,blocks)}\n')
    br=out/'vendor.new.dat.br'
    S.run(['brotli','-q','5','-o',str(br),str(image)],check=True)
    with tempfile.TemporaryDirectory() as tmp:
        p=P.Path(tmp); reconstructed=p/'roundtrip.img'
        unpack(br,tl,reconstructed,p)
        if digest(reconstructed)!=digest(image): raise ValueError('OTA roundtrip differs')
        fscheck(reconstructed)
    (out/'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in (br,tl)))
    (out/'STATUS.txt').write_text('UNTESTED: filesystem and OTA roundtrip only; device/HAL/AVB compatibility not validated.\n')
if __name__=='__main__': main()
