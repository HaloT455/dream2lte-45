#!/usr/bin/env python3
"""Audit two vendor images, then optionally replace explicitly reviewed regular files."""
import argparse, hashlib, json, os, pathlib as P, re, shutil, stat, subprocess as S, tempfile
B=4096
def run(*args, **kw): return S.run(args, check=True, **kw)
def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def ranges(s):
    n,*a=map(int,s.split(','))
    if n!=len(a) or not n or n%2: raise ValueError('invalid ranges')
    r=list(zip(a[::2],a[1::2]))
    if any(x<0 or y<=x for x,y in r) or any(y>z for (x,y),(z,t) in zip(r,r[1:])): raise ValueError('invalid bounds')
    return r
def transfer_commands(tl):
    l=tl.read_text().splitlines()
    if len(l)<5 or l[0] not in ('3','4'): raise ValueError('unsupported or truncated transfer list')
    if l[2:4]!=['0','0']: raise ValueError('incremental stash metadata unsupported')
    total=int(l[1]); cmds=[]
    for line in l[4:]:
        if not line.strip(): continue
        op,s=line.split()
        if op not in ('new','zero','erase'): raise ValueError('incremental list unsupported: '+op)
        cmds.append((op,ranges(s)))
    if not cmds: raise ValueError('empty transfer list')
    n=max(y for _,r in cmds for x,y in r)
    if n>1000000: raise ValueError('unexpectedly large image')
    allnew=sorted((x,y) for op,r in cmds if op=='new' for x,y in r)
    if any(y>z for (x,y),(z,t) in zip(allnew,allnew[1:])): raise ValueError('overlapping new ranges')
    newblocks=sum(y-x for x,y in allnew)
    # AOSP's second line counts writes, including zero blocks, not payload
    # blocks or partition capacity. Extended zero blocks may be excluded from
    # its progress total. Only `new` ranges consume bytes from .new.dat.br.
    writes=sum(y-x for op,r in cmds if op!='erase' for x,y in r)
    if not newblocks or not newblocks<=total<=writes: raise ValueError('invalid transfer progress block count')
    return cmds,newblocks,n
def unpack(br, tl, dst, temp):
    cmds,newblocks,n=transfer_commands(tl)
    dat=temp/'base.dat'
    run('brotli','-d','-o',str(dat),str(br))
    if dat.stat().st_size!=newblocks*B: raise ValueError('decompressed payload size mismatch')
    with open(dat,'rb') as src, open(dst,'xb') as out:
        out.truncate(n*B)
        for op,r in cmds:
            if op=='erase': continue  # new sparse file is already zero-filled
            for x,y in r:
                out.seek(x*B); left=(y-x)*B
                while left:
                    b=src.read(min(left,1024*1024)) if op=='new' else bytes(min(left,1024*1024))
                    if not b: raise EOFError('short data')
                    out.write(b); left-=len(b)
        if src.read(1): raise ValueError('extra payload')
    dat.unlink()
def filesystem(p):
    with open(p,'rb') as source:
        source.seek(1024); header=source.read(58)
    if header[:4]==bytes.fromhex('e2e1f5e0'): return 'erofs'
    if header[56:58]==bytes.fromhex('53ef'): return 'ext4'
    raise ValueError('unsupported vendor filesystem: '+str(p))
def fscheck(p):
    if filesystem(p)=='erofs': run('fsck.erofs','--extract',str(p))
    else: run('e2fsck','-f','-n',str(p))
def mount(p,d,ro):
    kind=filesystem(p)
    if kind=='erofs' and not ro: raise ValueError('EROFS is read-only; an explicit metadata-preserving rebuild is required')
    options='loop,ro,nodev,nosuid,noexec'+(',noload' if kind=='ext4' else '') if ro else 'loop,rw,nodev,nosuid,noexec'
    run('mount','-t',kind,'-o',options,str(p),str(d))
def meta(p):
    s=p.lstat()
    return {'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid,
            'xattrs':{k:os.getxattr(p,k,follow_symlinks=False).hex() for k in sorted(os.listxattr(p,follow_symlinks=False))}}
def inventory(root):
    result={}
    for d,ds,fs in os.walk(root,followlinks=False):
        for name in sorted(ds+fs):
            p=P.Path(d)/name; rel=p.relative_to(root).as_posix()
            s=p.lstat(); m=meta(p)
            if stat.S_ISREG(s.st_mode): m.update(kind='file',size=s.st_size,sha256=digest(p),nlink=s.st_nlink)
            elif stat.S_ISLNK(s.st_mode): m.update(kind='link',target=os.readlink(p))
            elif stat.S_ISDIR(s.st_mode): m.update(kind='dir')
            else: m.update(kind='special')
            result[rel]=m
    return result
def category(p):
    if re.search(r'(^|[/_.-])(ril|radio|ims|modem|rild|telephony|cbd|sim|lte)',p,re.I): return 'radio'
    if re.search(r'light|led|blink',p,re.I): return 'lights'
    if re.search(r'camera|gralloc',p,re.I): return 'camera'
    if re.search(r'codec|media|video|omx|stagefright|mfc',p,re.I): return 'media'
    return 'other'
def main():
    a=argparse.ArgumentParser()
    for arg in ('base','transfer','donor','out'): a.add_argument('--'+arg,type=P.Path,required=True)
    a.add_argument('--plan',type=P.Path,help='JSON array of reviewed paths + base_sha256 + donor_sha256')
    args=a.parse_args()
    args.out=args.out.resolve()
    if os.geteuid()!=0: raise SystemExit('Run as root on a trusted Linux VM/host (loop mounts).')
    args.out.mkdir(parents=True,exist_ok=True)
    base=args.out/'vendor-base.img'; output=args.out/'vendor-MERGED-UNTESTED.img'
    if base.exists() or output.exists(): raise SystemExit('Use an empty output directory')
    with tempfile.TemporaryDirectory() as t:
        temp=P.Path(t); unpack(args.base,args.transfer,base,temp)
        with args.donor.open('rb') as f: sparse=f.read(4)==bytes.fromhex('3aff26ed')
        donor=temp/'donor.raw' if sparse else args.donor.resolve()
        if sparse: run('simg2img',str(args.donor),str(donor))
        fscheck(base); fscheck(donor)
        (args.out/'input-provenance.json').write_text(json.dumps({
            'base_dat_br_sha256':digest(args.base), 'transfer_list_sha256':digest(args.transfer),
            'donor_input_sha256':digest(args.donor), 'base_image_sha256':digest(base),
            'base_filesystem':filesystem(base), 'donor_filesystem':filesystem(donor),
            'runtime_tested':False},indent=2)+'\n')
        m1=temp/'base';m2=temp/'donor';m1.mkdir();m2.mkdir()
        mounted=[]
        try:
            for image,dir in ((base,m1),(donor,m2)):
                mount(image,dir,True);mounted.append(dir)
            b=inventory(m1);d=inventory(m2)
            changes=[{'path':p,'category':category(p),'base':b.get(p),'donor':d.get(p)} for p in sorted(b.keys()|d.keys()) if b.get(p)!=d.get(p)]
            (args.out/'vendor-diff.json').write_text(json.dumps(changes,indent=2))
            print('Changed entries:',len(changes))
            for c in changes:
                if c['category']!='other': print(c['category'],c['path'])
            if not args.plan:
                print('Audit only; no merged image written. Review differences and dependencies first.')
                return
            if filesystem(base)!='ext4': raise ValueError('EROFS base audited only; refuse in-place writes without a metadata-preserving rebuild')
            plan=json.loads(args.plan.read_text())
            if not isinstance(plan,list) or not plan: raise ValueError('empty or invalid reviewed plan')
            chosen=set()
            for e in plan:
                p=e['path']
                if p in chosen or p not in b or p not in d: raise ValueError('invalid or duplicate path: '+p)
                chosen.add(p)
                old,new=b[p],d[p]
                if any(m['kind']!='file' or m['nlink']!=1 for m in (old,new)): raise ValueError('not an independent regular file: '+p)
                if old['sha256']!=e['base_sha256'] or new['sha256']!=e['donor_sha256']: raise ValueError('stale plan: '+p)
                if any(old[k]!=new[k] for k in ('uid','gid','mode','xattrs')): raise ValueError('metadata differs; manual port required: '+p)
            shutil.copyfile(base,output)
            run('umount',str(m1));mounted.remove(m1)
            mount(output,m1,False);mounted.append(m1)
            for p in sorted(chosen):
                target=m1/p;source=m2/p
                if target.resolve()!=target or source.resolve()!=source: raise ValueError('symlink path: '+p)
                with source.open('rb') as src,target.open('r+b') as dst:
                    shutil.copyfileobj(src,dst);dst.truncate();dst.flush();os.fsync(dst.fileno())
                if digest(target)!=d[p]['sha256'] or meta(target)!={k:b[p][k] for k in ('uid','gid','mode','xattrs')}: raise ValueError('post-write verification failed: '+p)
            actual=inventory(m1)
            expected={p:dict(b[p]) for p in b}
            # The base filesystem and metadata remain authoritative. Donor
            # compression/layout, inode counts and directory topology do not.
            for p in chosen: expected[p].update(size=d[p]['size'],sha256=d[p]['sha256'])
            if actual!=expected: raise ValueError('unexpected filesystem changes')
            run('umount',str(m1));mounted.remove(m1)
            fscheck(output)
            (args.out/'SHA256SUMS').write_text(digest(output)+'  '+output.name+'\n')
            print('Merged image filesystem validated; device/HAL/AVB compatibility NOT tested.')
        except BaseException:
            # Do not leave an apparently valid flash candidate after a failure.
            if output.exists(): output.rename(output.with_suffix('.FAILED'))
            raise
        finally:
            for m in reversed(mounted): run('umount',str(m))
if __name__=='__main__': main()
