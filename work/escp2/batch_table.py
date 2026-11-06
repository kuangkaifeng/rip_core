# -*- coding: utf-8 -*-
"""Batch table: mode params, pos0, advances, first printed paper row (=P0 if content starts at 0)."""
import sys, os, glob, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

def load(path):
    d = open(path, 'rb').read()
    return P.parse_job(d, decode=True)

def cum_units(job):
    pro = [int.from_bytes(bytes.fromhex(c["payload"])[:4], 'little')
           for c in job.prologue if c["name"].startswith("ESC(v")]
    cum = []; s = pro[0] if pro else 0
    for b in job.blocks:
        if b.advance is not None: s += b.advance
        cum.append(s)
    return cum

def row(job):
    pm = P.prologue_map(job)
    U = pm.get('ESC_U', {}); D = pm.get('ESC_D', {}); S = pm.get('ESC_S', {}); c = pm.get('ESC_c', {})
    pageunit = 2880 // U.get('a', 1)
    VSTEP = D.get('v', 1) * pageunit // 1440
    pos = cum_units(job)
    first = None
    for b in job.blocks:
        for r in range(90):
            if any(any(rec.raw[r*rec.n:(r+1)*rec.n]) for rec in b.records):
                p = pos[b.index] + VSTEP * r
                if first is None or p < first:
                    first = p
                break
    cols = ["%02x" % x.color for x in job.blocks[0].records]
    adv = collections.Counter(b.advance for b in job.blocks if b.advance is not None)
    return dict(U=(U.get('a'), U.get('b'), U.get('c')), D=(D.get('r'), D.get('v'), D.get('h')),
                S=(S.get('width'), S.get('height')), c=(c.get('a'), c.get('b')),
                pageunit=pageunit, VSTEP=VSTEP, pos0=pos[0], first=first,
                blocks=len(job.blocks), poslast=pos[-1],
                adv=dict(adv), colors="".join(cols),
                n=job.blocks[0].records[0].n,
                e=pm.get('ESC_e', {}).get('dot'), m=pm.get('ESC_m', {}).get('v'),
                i=pm.get('ESC_i', {}).get('v'), K=pm.get('ESC_K', {}).get('v'))

B = sys.argv[1] if len(sys.argv) > 1 else r"D:\work\RIP核心分析\reference\prn_samples"
files = sorted(glob.glob(os.path.join(B, "*.prn")))
print("%-46s %-6s %-8s %-11s %-11s %5s %5s %6s %6s %5s %s" % (
    "file", "U", "D(v,h)", "ESC(S) w,h", "ESC(c) a,b", "pos0", "first", "blocks", "poslast", "n", "adv"))
for f in files:
    try:
        job = load(f)
        r = row(job)
    except Exception as e:
        print("%-46s ERR %s" % (os.path.basename(f), e)); continue
    print("%-46s %-6s %-8s %-11s %-11s %5d %5d %6d %6d %5d %s  e=%s m=%s i=%s K=%s cols=%s" % (
        os.path.basename(f)[:46], r['U'], (r['D'][1], r['D'][2]), r['S'], r['c'],
        r['pos0'], r['first'], r['blocks'], r['poslast'], r['n'], r['adv'],
        r['e'], r['m'], r['i'], r['K'], r['colors']))
