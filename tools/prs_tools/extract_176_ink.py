#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract one ink's exact 1024x1024 threshold tile from its 176x176 256-level probe scans.

Usage: extract_176_ink.py <INK>    (INK = C,M,Y,K)
Output: reference/screen/tile_<INK>_1024.bin  (1024*1024*3 bytes [T1,T2,T3])
        reference/screen/tile_<INK>_meta.json (content_top etc.)
Convention: ESC/P2 2bit MSB-first, raster row -> page_row = 79*block + 8*row.
"""
import os, sys, json, math, collections, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
REF = os.path.join(ROOT, 'reference', 'screen')
TILE = 1024
CONTENT = 176*6  # 1056
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def scan_prn(P, fn, color):
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    pos = 0; rows = {}
    for blk in job.blocks:
        if blk.advance is not None: pos += blk.advance
        for rec in blk.records:
            if rec.color != color or not rec.raw: continue
            for r in range(rec.m):
                page_row = pos + 8*r
                chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                if len(chunk) < 264: continue
                vals = []
                for b in chunk:
                    vals.extend(UNPACK[b])
                old = rows.get(page_row)
                if old is None: rows[page_row] = vals
                else: rows[page_row] = [o if o else v for o, v in zip(old, vals)]
    return rows

def main():
    ink = sys.argv[1]
    P = load_parser()
    code = COLOR[ink]
    rows = scan_prn(P, os.path.join(SAMPLES, f'probe_scan_{ink}255_176_a3dtf1390_m2.prn'), code)
    nz = [r for r, v in rows.items() if any(v)]
    r0 = min(nz)
    print(f'{ink}: content top page row={r0}, rows with ink={len(nz)} (expect {CONTENT})', flush=True)
    T1 = [[0]*TILE for _ in range(TILE)]
    T2 = [[0]*TILE for _ in range(TILE)]
    T3 = [[0]*TILE for _ in range(TILE)]
    import time
    t0 = time.time()
    for t in range(1, 256):
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}_176_a3dtf1390_m2.prn')
        if not os.path.exists(fn):
            continue
        rows = scan_prn(P, fn, code)
        for y in range(TILE):
            vals = rows.get(r0 + y)
            if vals is None: continue
            T1y, T2y, T3y = T1[y], T2[y], T3[y]
            n = min(TILE, len(vals))
            for x in range(n):
                v = vals[x]
                if v:
                    if not T1y[x]: T1y[x] = t
                    if v >= 2 and not T2y[x]: T2y[x] = t
                    if v >= 3 and not T3y[x]: T3y[x] = t
        if t % 64 == 0:
            print(f'  t={t} ({time.time()-t0:.0f}s)', flush=True)
    miss = sum(1 for y in range(TILE) for x in range(TILE) if T1[y][x] == 0)
    print(f'{ink}: missing threshold pixels={miss}')
    data = bytearray()
    for y in range(TILE):
        for x in range(TILE):
            data.append(T1[y][x]); data.append(min(255, T2[y][x])); data.append(min(255, T3[y][x]))
    with open(os.path.join(REF, f'tile_{ink}_1024.bin'), 'wb') as f:
        f.write(data)
    meta = dict(ink=ink, content_top_page_row=r0, tile=TILE, missing=miss,
                source=f'probe_scan_{ink}###_176_a3dtf1390_m2.prn')
    with open(os.path.join(REF, f'tile_{ink}_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    print(f'saved reference/screen/tile_{ink}_1024.bin')

if __name__ == '__main__':
    main()
