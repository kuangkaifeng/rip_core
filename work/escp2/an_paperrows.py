# -*- coding: utf-8 -*-
"""Derive the paper-row model: paper_row(k,r) = pos_k + VSTEP*r; each printed once."""
import sys, collections
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

def paper_rows(path, col=0x00, VSTEP=8):
    job = load(path)
    pos = cum_units(job)
    rows = []          # (p, k, r)
    for b in job.blocks:
        rec = [x for x in b.records if x.color == col][0]
        for r in range(rec.m):
            if any(rec.raw[r*rec.n:(r+1)*rec.n]):
                rows.append((pos[b.index] + VSTEP*r, b.index, r))
    p = sorted(rows)
    print("=" * 90)
    print(path, "color %02x  printed rows=%d" % (col, len(p)))
    print("  paper row range: %d .. %d" % (p[0][0], p[-1][0]))
    vals = [x[0] for x in p]
    print("  unique paper rows:", len(set(vals)))
    # gaps
    gaps = collections.Counter(vals[i+1]-vals[i] for i in range(len(vals)-1))
    print("  gap histogram:", gaps.most_common(10))
    print("  first 20:", p[:20])
    print("  last 12:", p[-12:])
    # mod 8 distribution
    print("  p mod VSTEP:", collections.Counter(v % VSTEP for v in vals).most_common())
    return job, p

if __name__ == '__main__':
    paper_rows(r"D:\work\RIP核心分析\reference\prn_samples\a3dtf1390_flat_black_100_m2.prn")
    paper_rows(r"D:\work\RIP核心分析\reference\prn_samples\a3dtf1390_flat_black_100_m2.prn", 0x04)
    paper_rows(r"D:\work\RIP核心分析\reference\prn_samples\geomh_mode2.prn", 0x04)
