# -*- coding: utf-8 -*-
import sys, os, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

B = r"D:\work\RIP核心分析\reference\prn_samples"

def per_color_ink(path):
    d = open(path, 'rb').read()
    job = P.parse_job(d, decode=True)
    if not job.blocks:
        return None
    cols = [r.color for r in job.blocks[0].records]
    res = {}
    for col in cols:
        nz = 0
        vals = collections.Counter()
        for b in job.blocks:
            rec = [x for x in b.records if x.color == col][0]
            for r in range(rec.m):
                line = rec.raw[r*rec.n:(r+1)*rec.n]
                if any(line):
                    nz += 1
                    vals.update(line)
        res[col] = (nz, sum(vals.values()), vals.most_common(3))
    return len(job.blocks), res

for name in ['col_K', 'col_W', 'col_C', 'col_M', 'col_Y', 'col_R', 'col_G', 'col_B']:
    p = os.path.join(B, name + '_mode2.prn')
    if not os.path.exists(p):
        print(name, "missing"); continue
    r = per_color_ink(p)
    if r is None:
        print(name, "NO BLOCKS (blank job)"); continue
    nb, res = r
    print("%-6s blocks=%-3d " % (name, nb), end="")
    for col in sorted(res):
        nz, tot, top = res[col]
        print("| 0x%02x rows=%-4d bytes=%-7d top=%s " % (col, nz, tot, top[:2]), end="")
    print()
