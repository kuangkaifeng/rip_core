#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build the FINAL engine screen payload (1024x1024 tile, 4 channels):
 - C, Y: exact from 256-level 176x176 scans (content 1056x1056, covers whole 1024 tile)
 - M, K: exact from 256-level 64x64 scans in the top-left 384x384 region
         (so 64x64-input acceptance is pixel-exact), derived outside that region
         via D_M = 258 - D_C / D_K = 258 - D_Y.
Outputs: reference/screen, reference/screen/engine, build/screen (thr_<ink>.bin 1024^2*3,
D_<ink>.bin, screen_meta.json v3).
Also validates against lead's decoder convention (tools/validate/validate_e2e.py::decode_page).
"""
import os, sys, math, json, collections, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
REF = os.path.join(ROOT, 'reference', 'screen')
BUILD = os.path.join(ROOT, 'build', 'screen')
ENG = os.path.join(REF, 'engine')
TILE = 1024
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TOP64 = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def load_tile_thr(ink):
    d = open(os.path.join(REF, f'thr_{ink}.bin'), 'rb').read()
    assert len(d) == TILE*TILE*3, (ink, len(d))
    return [tuple(d[i*3:i*3+3]) for i in range(TILE*TILE)]

def extract_direct_384(ink):
    """exact T1/T2/T3 for content 384x384 from 64x64 probes (same convention as lead's decoder)."""
    P = load_parser()
    code = COLOR[ink]; top = TOP64[ink]; S = 384
    T = [[(0,0,0)]*S for _ in range(S)]
    T1 = [[0]*S for _ in range(S)]; T2 = [[0]*S for _ in range(S)]; T3 = [[0]*S for _ in range(S)]
    for t in range(1, 256):
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}_a3dtf1390_m2.prn')
        if not os.path.exists(fn): continue
        d = open(fn, 'rb').read()
        job = P.parse_job(d, decode=True)
        pos = 0; rows = {}
        for blk in job.blocks:
            if blk.advance is not None: pos += blk.advance
            for rec in blk.records:
                if rec.color != code or not rec.raw: continue
                for r in range(rec.m):
                    y = pos + 8*r - top
                    if not (0 <= y < S): continue
                    chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                    vals = []
                    for b in chunk[:96]:
                        vals.extend(UNPACK[b])
                    old = rows.get(y)
                    if old is None: rows[y] = vals
                    else: rows[y] = [o if o else v for o, v in zip(old, vals)]
        for y, vals in rows.items():
            for x in range(min(S, len(vals))):
                v = vals[x]
                if v:
                    if not T1[y][x]: T1[y][x] = t
                    if v >= 2 and not T2[y][x]: T2[y][x] = t
                    if v >= 3 and not T3[y][x]: T3[y][x] = t
    return T1, T2, T3

def D_from_thr(t):
    t1, t2, t3 = t
    lo, hi = 0, 255
    if t1: lo = max(lo, 256-3*t1); hi = min(hi, 258-3*t1)
    if t2: lo = max(lo, 512-3*t2); hi = min(hi, 514-3*t2)
    if t3: lo = max(lo, 768-3*t3); hi = min(hi, 770-3*t3)
    return lo, hi

def thr_from_D(d):
    t1 = max(1, min(255, math.ceil((256-d)/3)))
    t2 = max(1, min(255, math.ceil((512-d)/3)))
    t3 = math.ceil((768-d)/3)
    t3 = 0 if t3 > 255 else max(1, t3)
    return (t1, t2, t3)

def main():
    thrC = load_tile_thr('C'); thrY = load_tile_thr('Y')
    DC = [sum(D_from_thr(t))/2.0 for t in thrC]
    DY = [sum(D_from_thr(t))/2.0 for t in thrY]
    # direct M/K top-left region
    direct = {}
    for ink in ('M', 'K'):
        T1, T2, T3 = extract_direct_384(ink)
        direct[ink] = (T1, T2, T3)
        print(f'direct {ink} 384 region extracted')
    out = {'C': thrC, 'Y': thrY}
    for src, dst in (('C', 'M'), ('Y', 'K')):
        dsrc = DC if src == 'C' else DY
        tile = [None]*(TILE*TILE)
        T1, T2, T3 = direct[dst]
        for y in range(TILE):
            for x in range(TILE):
                i = y*TILE + x
                if x < 384 and y < 384:
                    t = (T1[y][x], T2[y][x], T3[y][x])
                    if t[0] == 0:
                        d = max(0, min(255, round(258 - dsrc[i])))
                        t = thr_from_D(d)
                    tile[i] = t
                else:
                    d = max(0, min(255, round(258 - dsrc[i])))
                    tile[i] = thr_from_D(d)
        out[dst] = tile
        print(f'{dst}: tile built (direct 384 region + derived elsewhere)')
    # write
    meta_channels = []
    for ink in ('C', 'M', 'Y', 'K'):
        data = bytearray()
        D = bytearray()
        for t in out[ink]:
            data.extend(t)
            lo, hi = D_from_thr(t)
            D.append(max(0, min(255, round((lo+hi)/2))))
        for base in (REF, BUILD, ENG):
            os.makedirs(base, exist_ok=True)
            with open(os.path.join(base, f'thr_{ink}.bin'), 'wb') as f:
                f.write(data)
            with open(os.path.join(base, f'D_{ink}.bin'), 'wb') as f:
                f.write(D)
        meta_channels.append(dict(ink=ink, file=f'thr_{ink}.bin', phaseX=0, phaseY=0,
                                  content_top_page_row=640 if ink in ('C', 'K') else 644,
                                  source=('256x176-level probe scan (exact)' if ink in ('C', 'Y')
                                          else '64x64 exact in top-left 384x384, derived (D=258-D) elsewhere')))
    meta = dict(
        version=3, size=TILE, tile_size=TILE,
        engine_rule='level(v,x,y) = (v>=T1)+(v>=T2)+(v>=T3); thr_<ink>.bin = size*size*3 bytes [T1,T2,T3] uint8 raster order y*size+x; 0 = never',
        coordinate_indexing=dict(type='content-relative',
                                 evidence='margin experiment 100% match at same content coords; D(x,y)=TILE[x%1024][y%1024]'),
        tile=dict(size=TILE, evidence='probe_scan_C64_720: lag 1024 equality 100.000%'),
        channels=meta_channels,
        validation=dict(
            probes_64px='C/M/Y/K x tones {0,16,64,128,192,240,255}: expected 100.000% (thresholds direct in 384 region)',
            probes_176px_CY='expected 100.000% (tile exact for C/Y)',
            decoder_convention='MSB-first 2bit, prow = pos_k + 8*r - content_top, merge nonzero (lead validator validate_e2e.py::decode_page)'),
        source='probe_scan_{C,Y}###_176 + probe_scan_{C,M,Y,K}### (64) 256-level scans, A3-DTF-1390.prs modeId=2')
    for base in (REF, BUILD, ENG):
        with open(os.path.join(base, 'screen_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
    print('final tile written to reference/screen, reference/screen/engine, build/screen')

    # ---- validate with LEAD's decoder ----
    spec = importlib.util.spec_from_file_location("validate_e2e", os.path.join(ROOT, 'tools', 'validate', 'validate_e2e.py'))
    V = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(V)
    except SystemExit:
        pass
    print('\n=== validation with lead decode_page (content=384 for 64px probes) ===')
    tones = (0, 16, 64, 128, 192, 240, 255)
    for ink in ('C', 'M', 'Y', 'K'):
        T = out[ink]
        worst = 100.0
        for t in tones:
            fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}_a3dtf1390_m2.prn')
            if not os.path.exists(fn): continue
            canvas = V.decode_page(fn, content=384)
            code = COLOR[ink]
            cv = canvas.get(code)
            if cv is None: continue
            mism = 0; tot = 0
            for y in range(384):
                for x in range(384):
                    T1, T2, T3 = T[y*TILE + x]
                    pred = (1 if t >= T1 > 0 else 0) + (1 if t >= T2 > 0 else 0) + (1 if t >= T3 > 0 else 0)
                    obs = cv[y][x]
                    tot += 1
                    if pred != obs: mism += 1
            acc = (tot-mism)*100.0/tot
            worst = min(worst, acc)
            print(f'  {ink} tone {t:3d}: match={acc:.4f}%')
        print(f'  {ink}: worst={worst:.4f}%')

if __name__ == '__main__':
    main()
