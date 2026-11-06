#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Decode a MainTop ESC/P2 .prn into per-color 2-bit dot planes.
Reuses tools/prn_tools/parse_prn.py (owned by escp2-analyst) if importable,
otherwise falls back to a local minimal parser.
Outputs a pickle/json summary to work/prs/.
"""
import os, sys, json, pickle
sys.setrecursionlimit(10000)

PRN = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"

def load_module(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("parse_prn", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def unpack2bit_msb(row):
    out = bytearray(len(row)*4)
    k = 0
    for b in row:
        out[k] = (b >> 6) & 3
        out[k+1] = (b >> 4) & 3
        out[k+2] = (b >> 2) & 3
        out[k+3] = b & 3
        k += 4
    return out

def main():
    d = open(PRN, 'rb').read()
    try:
        P = load_module(PARSE)
        job = P.parse_job(d, decode=True)
        blocks = []
        for blk in job.blocks:
            recs = {}
            for r in blk.records:
                recs[r.color] = r
            blocks.append(dict(advance=blk.advance, records=recs))
        print(f'parsed via escp2 tool: blocks={len(blocks)} warnings={len(job.warnings)}')
        prologue = job.prologue
    except Exception as e:
        print('escp2 tool import/parse failed:', e)
        raise
    # global stats per color
    stats = {}
    planes = {}
    for color in sorted({c for b in blocks for c in b['records']}):
        tot = 0; n = 0; hist = [0,0,0,0]
        allrows = []
        for bi, b in enumerate(blocks):
            r = b['records'].get(color)
            if r is None or r.raw is None:
                continue
            vals = unpack2bit_msb(r.raw)
            hist[0] += vals.count(0); hist[1] += vals.count(1)
            hist[2] += vals.count(2); hist[3] += vals.count(3)
            tot += sum(vals); n += len(vals)
            allrows.append(vals)
        stats[color] = dict(mean=(tot/n if n else 0), n=n, hist=hist,
                            meanfrac=(tot/n/3.0 if n else 0))
        planes[color] = allrows
        print(f'color 0x{color:02X}: mean={stats[color]["mean"]:.4f} mean/3={stats[color]["meanfrac"]:.4f} hist={hist} n={n}')
    out = dict(prn=PRN, prologue=prologue, stats={f'0x{k:02X}': v for k,v in stats.items()})
    os.makedirs(r'D:\work\RIP核心分析\work\prs', exist_ok=True)
    with open(r'D:\work\RIP核心分析\work\prs\golden_prn_stats.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print('saved stats -> work/prs/golden_prn_stats.json')
    # save planes pickle for later geometry analysis
    with open(r'D:\work\RIP核心分析\work\prs\golden_prn_planes.pkl', 'wb') as f:
        pickle.dump(dict(blocks=[(b['advance'], {c: r.raw for c, r in b['records'].items()}) for b in blocks]), f)
    print('saved planes -> work/prs/golden_prn_planes.pkl')

if __name__ == '__main__':
    main()
