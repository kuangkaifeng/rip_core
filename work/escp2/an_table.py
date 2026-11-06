# -*- coding: utf-8 -*-
"""Compact parameter table across the oracle corpus."""
import sys, os, glob, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

def info(path):
    d = open(path, 'rb').read()
    job = P.parse_job(d, decode=False)
    pm = P.prologue_map(job)
    pv = [int.from_bytes(bytes.fromhex(c["payload"])[:4], 'little')
          for c in job.prologue if c["name"].startswith("ESC(v")]
    nb = len(job.blocks)
    recs = [r for b in job.blocks for r in b.records]
    cols = []
    for b in job.blocks:
        for r in b.records:
            if r.color not in cols:
                cols.append(r.color)
    adv = collections.Counter(b.advance for b in job.blocks if b.advance is not None)
    nmset = set((r.n, r.m) for r in recs)
    U = pm.get('ESC_U', {}); D = pm.get('ESC_D', {}); S = pm.get('ESC_S', {}); c = pm.get('ESC_c', {})
    return dict(name=os.path.basename(path), size=len(d), blocks=nb, nrec=len(recs),
                U=(U.get('a'), U.get('b'), U.get('c')), D=(D.get('r'), D.get('v'), D.get('h')),
                S=(S.get('width'), S.get('height')), c=(c.get('a'), c.get('b')),
                pv=pv[:1], nmset=sorted(nmset), colors="".join("%02x" % x for x in cols),
                adv=adv.most_common(4), e=pm.get('ESC_e', {}).get('dot'),
                K=pm.get('ESC_K', {}).get('v'), m=pm.get('ESC_m', {}).get('v'))

files = sys.argv[1:]
if not files:
    files = sorted(glob.glob(r"D:\work\RIP核心分析\reference\prn_samples\a3dtf1390_*.prn"))
hdr = "%-42s %8s %4s %5s %-12s %-10s %-14s %-14s %-8s %-10s %-3s %-4s %s" % (
    "file", "size", "blk", "recs", "ESC(U abc)", "ESC(D r,v,h)", "ESC(S w,h)", "ESC(c a,b)",
    "colors", "advance", "e", "K", "n,m")
print(hdr)
print("-" * len(hdr))
for f in files:
    try:
        i = info(f)
    except Exception as ex:
        print("%-42s ERROR %s" % (os.path.basename(f), ex))
        continue
    print("%-42s %8d %4d %5d %-12s %-10s %-14s %-14s %-8s %-10s %-3s %-4s %s  pv=%s" % (
        i['name'], i['size'], i['blocks'], i['nrec'], i['U'], i['D'], i['S'], i['c'],
        i['colors'], i['adv'], i['e'], i['K'], i['nmset'], i['pv']))
