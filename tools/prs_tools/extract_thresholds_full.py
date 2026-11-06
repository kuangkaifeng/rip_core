#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract the full 1024x1024 stochastic screen tile from the 176x176 probe scans.

Input: reference/prn_samples/probe_scan_{C,Y}###_176_a3dtf1390_m2.prn (256 levels each)
       content = 1056x1056 device dots (176px @120dpi, 6 dots/px), mode2 720x720.
       record raster layout: page_row = 79*block + 8*raster_row (VSTEP=8).
Output: 1024x1024 tile:
   reference/screen/thr_<ink>.bin  = 1024*1024*3 bytes [T1,T2,T3] uint8 (0=never)
   reference/screen/D_<ink>.bin    = 1024*1024 uint8 threshold field D
   build/screen/ copies
M/K derived from C/Y via the measured complement relation D_M = 258 - D_C, D_K = 258 - D_Y
(validated ~99.6% against the direct 64x64 M/K extraction; exact for most pixels).
"""
import os, sys, json, math, collections, importlib.util, time
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
REF = os.path.join(ROOT, 'reference', 'screen')
BUILD = os.path.join(ROOT, 'build', 'screen')
TILE = 1024
IMG = 176
CONTENT = IMG*6      # 1056
VSTEP = 8
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

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
                page_row = pos + VSTEP*r
                chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                if len(chunk) < 264: continue
                vals = []
                for b in chunk:
                    vals.extend(UNPACK[b])
                old = rows.get(page_row)
                if old is None:
                    rows[page_row] = vals
                else:
                    rows[page_row] = [o if o else v for o, v in zip(old, vals)]
    return rows

def extract(ink, r0):
    P = load_parser()
    code = COLOR[ink]
    t0 = time.time()
    T1 = [[0]*TILE for _ in range(TILE)]
    T2 = [[0]*TILE for _ in range(TILE)]
    T3 = [[0]*TILE for _ in range(TILE)]
    for t in range(1, 256):
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}_176_a3dtf1390_m2.prn')
        if not os.path.exists(fn):
            print(f'  missing {fn}'); continue
        rows = scan_prn(P, fn, code)
        for y in range(TILE):
            pr = r0 + y
            vals = rows.get(pr)
            if vals is None: continue
            T1y, T2y, T3y = T1[y], T2[y], T3[y]
            for x in range(TILE):
                v = vals[x]
                if v:
                    if not T1y[x]: T1y[x] = t
                    if v >= 2 and not T2y[x]: T2y[x] = t
                    if v >= 3 and not T3y[x]: T3y[x] = t
        if t % 64 == 0:
            print(f'  {ink} t={t} ({time.time()-t0:.0f}s)', flush=True)
    # derive D
    D = [[0]*TILE for _ in range(TILE)]
    amb = collections.Counter(); miss = 0
    for y in range(TILE):
        for x in range(TILE):
            t1, t2, t3 = T1[y][x], T2[y][x], T3[y][x]
            if not t1: miss += 1; continue
            cand = set(range(256-3*t1, 260-3*t1))
            if t2: cand &= set(range(512-3*t2, 516-3*t2))
            if t3: cand &= set(range(768-3*t3, 772-3*t3))
            cand = {c for c in cand if 0 <= c <= 255}
            amb[len(cand)] += 1
            if cand: D[y][x] = int(round(sum(cand)/len(cand)))
    print(f'{ink}: miss={miss}, D candidates={amb.most_common(4)}')
    return T1, T2, T3, D

def write_tile(ink, T1, T2, T3, D):
    data = bytearray()
    for y in range(TILE):
        for x in range(TILE):
            data.append(T1[y][x]); data.append(min(255, T2[y][x])); data.append(min(255, T3[y][x]))
    for base in (REF, BUILD, os.path.join(REF, 'engine')):
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, f'thr_{ink}.bin'), 'wb') as f:
            f.write(data)
        with open(os.path.join(base, f'D_{ink}.bin'), 'wb') as f:
            f.write(bytes(D[y][x] for y in range(TILE) for x in range(TILE)))

def derive_from(baseD, offset=258):
    """thresholds from D via Tk=ceil((k*256-D)/3), D' = offset - D."""
    T1 = [[0]*TILE for _ in range(TILE)]
    T2 = [[0]*TILE for _ in range(TILE)]
    T3 = [[0]*TILE for _ in range(TILE)]
    D = [[0]*TILE for _ in range(TILE)]
    for y in range(TILE):
        for x in range(TILE):
            d = offset - baseD[y][x]
            d = max(0, min(255, d))
            D[y][x] = d
            t1 = math.ceil((256-d)/3); t2 = math.ceil((512-d)/3); t3 = math.ceil((768-d)/3)
            T1[y][x] = max(1, min(255, t1))
            T2[y][x] = max(1, min(255, t2))
            if t3 > 255: T3[y][x] = 0
            else: T3[y][x] = max(1, t3)
    return T1, T2, T3, D

def main():
    # find content top for C and Y from t=255
    P = load_parser()
    tops = {}
    for ink in ('C', 'Y'):
        rows = scan_prn(P, os.path.join(SAMPLES, f'probe_scan_{ink}255_176_a3dtf1390_m2.prn'), COLOR[ink])
        nz = [r for r, v in rows.items() if any(v)]
        tops[ink] = min(nz)
        print(f'{ink}: content top page row={tops[ink]}, rows={len(nz)} (expect {CONTENT})')
    tiles = {}
    for ink in ('C', 'Y'):
        print(f'--- extracting {ink} 1024x1024 tile ---', flush=True)
        T1, T2, T3, D = extract(ink, tops[ink])
        tiles[ink] = (T1, T2, T3, D)
        write_tile(ink, T1, T2, T3, D)
        print(f'  wrote thr_{ink}.bin (1024x1024x3)')
    # derive M from C, K from Y
    for src, dst in (('C', 'M'), ('Y', 'K')):
        T1, T2, T3, D = derive_from(tiles[src][3])
        write_tile(dst, T1, T2, T3, D)
        print(f'  wrote thr_{dst}.bin derived from {src} (D_{dst} = 258 - D_{src})')
    # meta v3
    meta = dict(
        version=3, size=TILE, tile_size=TILE,
        engine_rule='level(v,x,y) = (v>=T1)+(v>=T2)+(v>=T3); thr_<ink>.bin = size*size*3 bytes [T1,T2,T3] uint8 raster order y*size+x; 0 = never',
        coordinate_indexing=dict(type='content-relative',
                                 evidence='margin experiment: 100% level match at same content coords; D(x,y)=TILE[x%1024][y%1024]'),
        tile=dict(size=TILE, evidence='probe_scan_C64_720: lag 1024 equality 100.000% in x and y'),
        channels=[
            dict(ink='C', file='thr_C.bin', content_top_page_row=tops['C'], source='256-level 176x176 probe scan'),
            dict(ink='Y', file='thr_Y.bin', content_top_page_row=tops['Y'], source='256-level 176x176 probe scan'),
            dict(ink='M', file='thr_M.bin', content_top_page_row=tops['Y'],
                 source='derived: D_M = 258 - D_C (complement relation; ~99.6% exact vs direct extraction)'),
            dict(ink='K', file='thr_K.bin', content_top_page_row=tops['Y'],
                 source='derived: D_K = 258 - D_Y'),
        ],
        phase_note='C content top page row vs M/Y differ (+4 page rows observed in 64px probes); engine must apply per-channel raster phase.',
        validation=dict(
            C_Y='100.000% expected vs probe PRNs at content coords (extraction is transition-exact)',
            M_K='~99.6% vs direct 64x64 extraction (complement relation)',
        ),
        source='probe_scan_{C,Y}###_176_a3dtf1390_m2.prn (256 levels), A3-DTF-1390.prs modeId=2',
    )
    for base in (REF, BUILD, os.path.join(REF, 'engine')):
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, 'screen_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
    print('done: full 1024x1024 tile written')

if __name__ == '__main__':
    main()
