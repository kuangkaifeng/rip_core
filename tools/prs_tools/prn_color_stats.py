#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Accurate per-color dot stats for ESC/P2 PRNs: fractions + linear coverage."""
import sys, os, importlib.util

PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

def load():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def color_stats(fn, P):
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    out = {}
    for blk in job.blocks:
        for r in blk.records:
            if r.raw is None: continue
            s = out.setdefault(r.color, [0,0,0,0]); n = 0
            for b in r.raw:
                for v in UNPACK[b]:
                    s[v] += 1
            out[r.color] = s
    res = {}
    for c, hs in sorted(out.items()):
        n = sum(hs)
        frac = [h/n for h in hs]
        res['0x%02X' % c] = dict(hist=hs, frac=[round(f,4) for f in frac], n=n,
                                 linear=round(frac[1]/3+frac[2]*2/3+frac[3], 4),
                                 mean=round((frac[1]+2*frac[2]+3*frac[3]), 4))
    return res, len(job.blocks)

if __name__ == '__main__':
    P = load()
    for fn in sys.argv[1:]:
        try:
            res, nb = color_stats(fn, P)
        except Exception as e:
            print(f'{os.path.basename(fn)}: ERR {e}'); continue
        print(f"{os.path.basename(fn)} blocks={nb}")
        for c, v in res.items():
            print(f"   {c} n={v['n']:8d} hist={v['hist']} linear={v['linear']:.3f} frac={v['frac']}")
