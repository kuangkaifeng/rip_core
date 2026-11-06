#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Geometry-free ink coverage measurement per color record using block-local content mask.

For each block of an ESC/P2 PRN: all color records share the same raster geometry.
mask = union of nonzero dots over the color records of that block.
coverage(plane) = mean(level)/3 over mask, averaged over blocks (weighted by mask size).
This cancels the unknown page-content geometry.
"""
import sys, os, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

def load():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def main(fn):
    P = load()
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    # per color: sum level and count over mask
    acc = {}
    for blk in job.blocks:
        recs = [r for r in blk.records if r.raw]
        if not recs: continue
        # assume all same n,m
        n = recs[0].n; m = recs[0].m
        rows = {r.color: [UNPACK2(b) for b in r.raw] for r in recs}
        # union mask via byte>0
        for r in recs:
            s = acc.setdefault(r.color, [0, 0])   # level sum, mask count
            pass
        # compute mask per row from any nonzero byte
        for row in range(m):
            off = row*n
            mask = [False]*(n*4)
            anynz = False
            for r in recs:
                chunk = r.raw[off:off+n]
                for i, b in enumerate(chunk):
                    if b:
                        anynz = True
                        u = UNPACK[b]
                        base = i*4
                        if u[0]: mask[base] = True
                        if u[1]: mask[base+1] = True
                        if u[2]: mask[base+2] = True
                        if u[3]: mask[base+3] = True
            if not anynz: continue
            cnt = sum(mask)
            if not cnt: continue
            for r in recs:
                chunk = r.raw[off:off+n]
                tot = 0
                for i, b in enumerate(chunk):
                    u = UNPACK[b]
                    base = i*4
                    if mask[base]: tot += u[0]
                    if mask[base+1]: tot += u[1]
                    if mask[base+2]: tot += u[2]
                    if mask[base+3]: tot += u[3]
                a = acc[r.color]
                a[0] += tot; a[1] += cnt
    res = {}
    for c, (s, n) in sorted(acc.items()):
        res['0x%02X' % c] = dict(sum=s, cnt=n, linear=round(s/(3.0*n), 4) if n else 0)
    return res, len(job.blocks)

UNPACK2 = None

def main2(fn):
    global UNPACK2
    P = load()
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    acc = {}
    for blk in job.blocks:
        recs = [r for r in blk.records if r.raw]
        if not recs: continue
        n = recs[0].n; m = recs[0].m
        for row in range(m):
            off = row*n
            mask = bytearray(n*4)
            anynz = False
            for r in recs:
                chunk = r.raw[off:off+n]
                for i, b in enumerate(chunk):
                    if b:
                        anynz = True
                        base = i*4
                        u = UNPACK[b]
                        mask[base] |= 1 if u[0] else 0
                        mask[base+1] |= 1 if u[1] else 0
                        mask[base+2] |= 1 if u[2] else 0
                        mask[base+3] |= 1 if u[3] else 0
            if not anynz: continue
            cnt = sum(mask)
            if not cnt: continue
            for r in recs:
                chunk = r.raw[off:off+n]
                tot = 0
                for i, b in enumerate(chunk):
                    u = UNPACK[b]
                    base = i*4
                    if mask[base]: tot += u[0]
                    if mask[base+1]: tot += u[1]
                    if mask[base+2]: tot += u[2]
                    if mask[base+3]: tot += u[3]
                a = acc.setdefault(r.color, [0, 0])
                a[0] += tot; a[1] += cnt
    res = {}
    for c, (s, n) in sorted(acc.items()):
        res['0x%02X' % c] = dict(sum=s, cnt=n, linear=round(s/(3.0*n), 4) if n else 0)
    return res, len(job.blocks)

if __name__ == '__main__':
    for fn in sys.argv[1:]:
        try:
            res, nb = main2(fn)
        except Exception as e:
            print(f'{os.path.basename(fn)}: ERR {e}'); continue
        print(f"{os.path.basename(fn)} blocks={nb}")
        for c, v in res.items():
            print(f"   {c} mask_dots={v['cnt']:8d} sum={v['sum']:9d} coverage={v['linear']:.4f}")
