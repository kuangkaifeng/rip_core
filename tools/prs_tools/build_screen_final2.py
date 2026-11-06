#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FINAL engine screen payload builder (v3, 1024 tile).

Convention = lead's decoder (tools/validate/validate_e2e.py::decode_page):
  ESC/P2 2bit MSB-first; content_top C/K=640, M/Y=644; prow = pos_k + 8*r - top;
  nonzero-merge across blocks.

Data sources:
  C, Y: 256-level 176x176 probe scans -> exact 1024x1024 tile (already extracted in
        reference/screen/thr_{C,Y}.bin by extract_thresholds_full.py; that extraction
        uses the identical MSB/tops/8*r convention and was verified against the decoder).
  M, K: 256-level 64x64 probe scans -> exact in top-left 384x384 (extracted here with
        lead's decode_page, so bit-identical convention); derived elsewhere via
        D_M = 258 - D_C, D_K = 258 - D_Y (measured 99.6% exact on the direct region).
Output: reference/screen/, reference/screen/engine/, build/screen/ (size=1024),
        reference/screen/legacy384/ (size=384, for old engine builds).
"""
import os, sys, math, json, importlib.util
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
REF = os.path.join(ROOT, 'reference', 'screen')
BUILD = os.path.join(ROOT, 'build', 'screen')
ENG = os.path.join(REF, 'engine')
LEG = os.path.join(REF, 'legacy384')
TILE = 1024
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}
TONES = (0, 16, 64, 128, 192, 240, 255)

def load_lead_decoder():
    spec = importlib.util.spec_from_file_location("validate_e2e", os.path.join(ROOT, 'tools', 'validate', 'validate_e2e.py'))
    V = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(V)
    except SystemExit:
        pass
    return V

def load_thr_file(path, size):
    d = open(path, 'rb').read()
    assert len(d) == size*size*3, (path, len(d), size)
    return [tuple(d[i*3:i*3+3]) for i in range(size*size)]

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

def extract_direct_384(V, ink):
    code = COLOR[ink]
    S = 384
    T1 = [[0]*S for _ in range(S)]
    T2 = [[0]*S for _ in range(S)]
    T3 = [[0]*S for _ in range(S)]
    for t in range(1, 256):
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}_a3dtf1390_m2.prn')
        if not os.path.exists(fn):
            continue
        cv = V.decode_page(fn, content=S).get(code)
        if cv is None:
            continue
        for y in range(S):
            row = cv[y]
            T1y, T2y, T3y = T1[y], T2[y], T3[y]
            for x in range(S):
                v = row[x]
                if v:
                    if not T1y[x]: T1y[x] = t
                    if v >= 2 and not T2y[x]: T2y[x] = t
                    if v >= 3 and not T3y[x]: T3y[x] = t
    return T1, T2, T3

def val_report(V, ink, tile, tone, content):
    fn = os.path.join(SAMPLES, f'probe_scan_{ink}{tone:03d}' + ('_176' if content > 1000 else '') + '_a3dtf1390_m2.prn')
    if not os.path.exists(fn):
        return None
    cv = V.decode_page(fn, content=content).get(COLOR[ink])
    if cv is None:
        return None
    N = min(content, TILE)
    mism = 0
    for y in range(N):
        row = cv[y]
        for x in range(N):
            T1, T2, T3 = tile[y*TILE + x]
            pred = (1 if tone >= T1 > 0 else 0) + (1 if tone >= T2 > 0 else 0) + (1 if tone >= T3 > 0 else 0)
            if pred != row[x]:
                mism += 1
    return (N*N-mism)*100.0/(N*N)

def main():
    V = load_lead_decoder()
    print('loading C/Y exact 1024 tile from reference/screen ...')
    tiles = {}
    tiles['C'] = load_thr_file(os.path.join(REF, 'thr_C.bin'), TILE)
    tiles['Y'] = load_thr_file(os.path.join(REF, 'thr_Y.bin'), TILE)
    for k in ('C', 'Y'):
        miss = sum(1 for t in tiles[k] if t[0] == 0)
        print(f'  {k}: missing threshold pixels = {miss}')
    print('extracting M/K direct 384 region via lead decoder ...', flush=True)
    direct = {}
    for ink in ('M', 'K'):
        T1, T2, T3 = extract_direct_384(V, ink)
        direct[ink] = (T1, T2, T3)
        miss = sum(1 for y in range(384) for x in range(384) if T1[y][x] == 0)
        print(f'  {ink}: direct 384 extracted, missing={miss}')
    # assemble tile
    for dst, src in (('M', 'C'), ('K', 'Y')):
        Srctile = tiles[src]
        T1, T2, T3 = direct[dst]
        tile = []
        for y in range(TILE):
            for x in range(TILE):
                i = y*TILE + x
                if x < 384 and y < 384 and T1[y][x] != 0:
                    tile.append((T1[y][x], T2[y][x], T3[y][x]))
                else:
                    lo, hi = D_from_thr(Srctile[i])
                    d = 258 - (lo+hi)/2.0
                    tile.append(thr_from_D(max(0, min(255, round(d)))))
        tiles[dst] = tile
        print(f'  {dst}: tile assembled')
    # write payloads
    def write_set(base, size):
        os.makedirs(base, exist_ok=True)
        chans = []
        for ink in ('C', 'M', 'Y', 'K'):
            it = tiles[ink]
            data = bytearray()
            for y in range(size):
                for x in range(size):
                    data.extend(it[y*TILE + x])
            with open(os.path.join(base, f'thr_{ink}.bin'), 'wb') as f:
                f.write(data)
            chans.append(dict(ink=ink, file=f'thr_{ink}.bin',
                              content_top_page_row=TOP[ink]))
        meta = dict(
            version=3, size=size, tile_size=TILE,
            engine_rule='level(v,x,y) = (v>=T1)+(v>=T2)+(v>=T3); thr_<ink>.bin = size*size*3 bytes [T1,T2,T3] uint8 raster order y*size+x; 0=never',
            coordinate_indexing=dict(type='content-relative',
                                     evidence='D(x,y)=TILE[x%1024][y%1024]; margin experiment 100% match at same content coords'),
            tile=dict(size=TILE, evidence='probe_scan_C64_720: lag-1024 level equality 100.000% in x and y'),
            channels=chans,
            decoder_convention='ESC/P2 2bit MSB-first; prow = pos_k + 8*r - content_top; nonzero merge; matches tools/validate/validate_e2e.py::decode_page',
            validation='see work/prs/build_screen_final2.log (C/M/Y/K 64px probes + C/Y 176px probes, lead decoder)',
            source='probe_scan_{C,Y}###_176 + probe_scan_{C,M,Y,K}###(64), 256 levels, A3 modeId=2')
        with open(os.path.join(base, 'screen_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
    write_set(REF, TILE)
    write_set(ENG, TILE)
    write_set(BUILD, TILE)
    write_set(LEG, 384)
    print('written: build/screen, reference/screen, reference/screen/engine (1024); reference/screen/legacy384 (384)')
    # validation
    print('\n=== validation under lead decoder: 64px probes content=384 ===')
    worst = 100.0
    for ink in ('C', 'M', 'Y', 'K'):
        cw = 100.0
        for t in TONES:
            acc = val_report(V, ink, tiles[ink], t, 384)
            if acc is None: continue
            cw = min(cw, acc)
            print(f'  {ink} tone {t:3d}: {acc:.4f}%')
        print(f'  {ink}: worst={cw:.4f}%')
        worst = min(worst, cw)
    print(f'worst overall (64px) = {worst:.4f}%')
    print('\n=== validation under lead decoder: 176px C/Y probes content=1056 (region 1024) ===')
    for ink in ('C', 'Y'):
        cw = 100.0
        for t in TONES:
            acc = val_report(V, ink, tiles[ink], t, 1056)
            if acc is None: continue
            cw = min(cw, acc)
            print(f'  {ink} tone {t:3d}: {acc:.4f}%')
        print(f'  {ink}: worst={cw:.4f}%')

if __name__ == '__main__':
    main()
