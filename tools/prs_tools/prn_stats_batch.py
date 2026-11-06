#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Batch decode .prn -> per-color dot stats (mean/hist). Usage: prn_stats_batch.py file1 [file2 ...]"""
import sys, os, json, importlib.util

PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"

def load_module(path):
    spec = importlib.util.spec_from_file_location("parse_prn", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

def stats(fn, P):
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    per = {}
    for blk in job.blocks:
        for r in blk.records:
            if r.raw is None:
                continue
            s = per.setdefault(r.color, dict(n=0, sum=0, hist=[0,0,0,0]))
            # fast counts
            n = len(r.raw)*4
            s['n'] += n
            hs = [0,0,0,0]
            for b in r.raw:
                for v in UNPACK[b]:
                    hs[v] += 1
            for i in range(4):
                s['hist'][i] += hs[i]
            s['sum'] += hs[1] + 2*hs[2] + 3*hs[3]
    out = {}
    for c, s in sorted(per.items()):
        out['0x%02X' % c] = dict(mean=s['sum']/s['n'] if s['n'] else 0.0,
                                 hist=s['hist'], n=s['n'],
                                 frac=[h/s['n'] for h in s['hist']])
    return out, len(job.blocks)

if __name__ == '__main__':
    P = load_module(PARSE)
    for fn in sys.argv[1:]:
        try:
            out, nb = stats(fn, P)
        except Exception as e:
            print(f'{os.path.basename(fn)}: ERROR {e}')
            continue
        parts = []
        for c, v in out.items():
            parts.append(f"{c}:m={v['mean']:.3f}[{v['hist'][1]},{v['hist'][2]},{v['hist'][3]}]")
        print(f"{os.path.basename(fn):48s} blocks={nb:4d} " + ' '.join(parts))
