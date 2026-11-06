#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Patch the M/K tile positions that ended with T=0: re-derive their thresholds by a UNION
over all raster positions that map to the same page row (some pixels are carried by a
different block/record than the first mapping found).
"""
import os, sys, json, importlib.util
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
REF = os.path.join(ROOT, 'reference', 'screen')
FINAL = os.path.join(REF, 'final')
TILE = 1024
PARSE = os.path.join(ROOT, 'tools', 'prn_tools', 'parse_prn.py')
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def load_tile(ink):
    return bytearray(open(os.path.join(FINAL, f'thr_{ink}.bin'), 'rb').read())

def holes_of(tile):
    return [(i//TILE, i % TILE) for i in range(TILE*TILE) if tile[i*3] == 0]

def patch(ink, r0):
    tile = load_tile(ink)
    holes = holes_of(tile)
    print(f'{ink}: holes={len(holes)} r0={r0}')
    if not holes:
        return tile, 0
    # target page rows
    targets = {}
    for (y, x) in holes:
        targets.setdefault(r0 + y, []).append((y, x))
    print(f'  target page rows: {len(targets)}')
    P = load_parser()
    code = COLOR[ink]
    T1 = {}; T2 = {}; T3 = {}
    for t in range(1, 256):
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}_176_a3dtf1390_m2.prn')
        if not os.path.exists(fn): continue
        d = open(fn, 'rb').read()
        job = P.parse_job(d, decode=True)
        pos = 0
        for blk in job.blocks:
            if blk.advance is not None: pos += blk.advance
            for rec in blk.records:
                if rec.color != code or not rec.raw: continue
                for r in range(rec.m):
                    page_row = pos + 8*r
                    tgt = targets.get(page_row)
                    if not tgt: continue
                    chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                    if len(chunk) < 264: continue
                    vals = []
                    for b in chunk:
                        vals.extend(UNPACK[b])
                    for (y, x) in tgt:
                        if x >= len(vals): continue
                        v = vals[x]
                        if v:
                            key = (y, x)
                            if key not in T1: T1[key] = t
                            if v >= 2 and key not in T2: T2[key] = t
                            if v >= 3 and key not in T3: T3[key] = t
        if t % 64 == 0:
            print(f'  {ink} t={t}', flush=True)
    patched = 0
    for (y, x) in holes:
        key = (y, x)
        t1 = T1.get(key, 0); t2 = T2.get(key, 0); t3 = T3.get(key, 0)
        if t1:
            o = (y*TILE + x)*3
            tile[o] = t1; tile[o+1] = t2 if t2 else 0; tile[o+2] = t3 if t3 else 0
            patched += 1
    print(f'  {ink}: patched {patched}/{len(holes)} holes')
    return tile, patched

def main():
    patched_total = 0
    for ink, r0 in (('M', 644), ('K', 640)):
        tile, n = patch(ink, r0)
        open(os.path.join(FINAL, f'thr_{ink}.bin'), 'wb').write(tile)
        patched_total += n
    print(f'total patched={patched_total}')
    # rebuild D for patched channels
    for ink in ('M', 'K'):
        d = open(os.path.join(FINAL, f'thr_{ink}.bin'), 'rb').read()
        D = bytearray()
        for i in range(TILE*TILE):
            t1, t2, t3 = d[i*3], d[i*3+1], d[i*3+2]
            lo, hi = 0, 255
            if t1: lo = max(lo, 256-3*t1); hi = min(hi, 258-3*t1)
            if t2: lo = max(lo, 512-3*t2); hi = min(hi, 514-3*t2)
            if t3: lo = max(lo, 768-3*t3); hi = min(hi, 770-3*t3)
            D.append(max(0, min(255, round((lo+hi)/2))))
        open(os.path.join(FINAL, f'D_{ink}.bin'), 'wb').write(D)

if __name__ == '__main__':
    main()
