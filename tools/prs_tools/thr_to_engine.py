#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Convert T1's raster-position threshold scan (probe_scan_thresholds.bin) into
page-space screen data for the engine.

Input bin layout (verified):
  3 x 449280 uint16 arrays = [T1][T2][T3], raster-position indexed as
  13 blocks x 90 raster rows x 384 cols; page_row = 79*block + 8*row (mode2 VSTEP=8),
  page pixels = page rows 640..1023 (384) x cols 0..383.
  value 0 == "transition never happens".
  engine rule: level(v) = (v>=T1) + (v>=T2) + (v>=T3), v = 0..255 ink value.

Output (lead-specified format):
  reference/screen/screen_meta.json
  reference/screen/thr_C.bin   = 384*384*3 bytes: per pixel [T1,T2,T3] uint8, raster order y*384+x
Also derives D (0..255) where possible: T1 = ceil((256-D)/3) => D in [256-3*T1, 258-3*T1]
 and cross-checks with 16-tone level matrices.
"""
import os, sys, array, json, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
os.environ['PRN_UNPACK'] = 'msb'
import prn_canvas

ROOT = r"D:\work\RIP核心分析"
BIN = os.path.join(ROOT, 'work', 'protocol', 'evidence', 'probe_scan_thresholds.bin')
OUT = os.path.join(ROOT, 'reference', 'screen')
N = 449280
W = 384
VSTEP = 8
PAGE_ROW0 = 640
SIZE = 384

def load_thresholds():
    d = open(BIN, 'rb').read()
    assert len(d) == 3*N*2, len(d)
    arrs = []
    for i in range(3):
        a = array.array('H')
        a.frombytes(d[i*N*2:(i+1)*N*2])
        arrs.append(a)
    return arrs

def raster_to_page():
    """Return list of (raster_index, page_y, page_x) for page pixels."""
    m = []
    for blk in range(13):
        pos = 79*blk
        for r in range(90):
            py = pos + VSTEP*r
            if PAGE_ROW0 <= py <= PAGE_ROW0 + SIZE - 1:
                y = py - PAGE_ROW0
                for x in range(W):
                    m.append(((blk*90 + r)*W + (4*(x//4) + 3-(x%4)), y, x))
    return m

def main():
    os.makedirs(OUT, exist_ok=True)
    T1, T2, T3 = load_thresholds()
    mapping = raster_to_page()
    print(f'page pixels: {len(mapping)} (expect {SIZE*SIZE})')
    ys = set(); rows_used = set()
    pageT = [[[0, 0, 0] for _ in range(SIZE)] for _ in range(SIZE)]
    conflicts = 0
    for idx, y, x in mapping:
        t = (T1[idx], T2[idx], T3[idx])
        if any(t):
            if any(pageT[y][x]):
                conflicts += 1
            pageT[y][x] = [t[0], t[1], t[2]]
    nz = sum(1 for y in range(SIZE) for x in range(SIZE) if any(pageT[y][x]))
    print(f'page pixels with thresholds: {nz} ({nz*100.0/(SIZE*SIZE):.2f}%), conflicts={conflicts}')
    # check monotone T1<T2<T3 (unless 0=never)
    bad = 0
    for y in range(SIZE):
        for x in range(SIZE):
            t1, t2, t3 = pageT[y][x]
            if not (0 < t1 <= t2 <= t3 or (t2 == 0 and t3 == 0)):
                bad += 1
    print(f'non-monotone triples: {bad}')
    # derive D candidates
    dvals = [[-1]*SIZE for _ in range(SIZE)]
    ambig = collections.Counter()
    for y in range(SIZE):
        for x in range(SIZE):
            t1, t2, t3 = pageT[y][x]
            if t1 == 0:
                continue
            cand = set(range(256-3*t1, 258-3*t1+1))
            if t2:
                cand &= set(range(512-3*t2, 514-3*t2+1))
            if t3:
                cand &= set(range(768-3*t3, 770-3*t3+1))
            cand = {c for c in cand if 0 <= c <= 255}
            ambig[len(cand)] += 1
            if cand:
                dvals[y][x] = sum(cand)/len(cand)
    print('D candidate-set size distribution:', ambig.most_common(6))
    # write thr_C.bin
    data = bytearray()
    for y in range(SIZE):
        for x in range(SIZE):
            for v in pageT[y][x]:
                data.append(min(255, v))
    with open(os.path.join(OUT, 'thr_C.bin'), 'wb') as f:
        f.write(data)
    # write D (uint8 midpoint) for analysis
    with open(os.path.join(OUT, 'D_C_uint8.bin'), 'wb') as f:
        f.write(bytes(max(0, min(255, round(dvals[y][x]))) for y in range(SIZE) for x in range(SIZE)))
    meta = dict(
        size=SIZE,
        source=dict(bin=os.path.relpath(BIN, ROOT), layout='3 x 449280 uint16 [T1][T2][T3], raster (13 blocks x 90 rows x 384 cols), page_row=79*block+8*row, page pixels rows 640..1023',
                    thresholds_units='ink value 0..255; 0 = transition never',
                    engine_rule='level(v) = (v>=T1)+(v>=T2)+(v>=T3)'),
        channels=[dict(ink='C', file='thr_C.bin', phaseX=0, phaseY=0,
                       coverage='static 384x384 page region')],
        d_file=dict(file='D_C_uint8.bin', format='384*384 uint8 row-major, D midpoint (255 if unknown)'),
        notes='C channel from 256-level probe scan (T1); M/Y/K pending (32-level approx or 256-level).')
    with open(os.path.join(OUT, 'screen_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    print('saved reference/screen/{thr_C.bin,D_C_uint8.bin,screen_meta.json}')
    # cross-check with level matrices for known tones from probe PRNs
    COLOR = {'C': 0x00}
    SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
    for tone in (16, 32, 64, 128, 192, 240, 255):
        cands = [os.path.join(SAMPLES, f'probe_screen_probe_C{tone}_a3dtf1390_m2.prn'),
                 os.path.join(SAMPLES, f'probe_sweep_C{tone}_a3dtf1390_m2.prn')]
        fn = next((c for c in cands if os.path.exists(c)), None)
        if fn is None: continue
        os.environ.setdefault('PRN_UNPACK','msb'); cvs, info = prn_canvas.decode_canvas(fn, vstep=VSTEP, verbose=False)
        cv = cvs.get(0)
        mism = 0; total = 0; nzlev = 0
        for y in range(SIZE):
            for x in range(SIZE):
                obs = cv[PAGE_ROW0 + y][x]
                t1, t2, t3 = pageT[y][x]
                pred = (1 if tone >= t1 > 0 else 0) + (1 if tone >= t2 > 0 else 0) + (1 if tone >= t3 > 0 else 0)
                total += 1
                if pred != obs:
                    mism += 1
                if obs: nzlev += 1
        print(f'tone {tone:3d}: match={(total-mism)*100.0/total:.3f}% obs_nonzero={nzlev}')

if __name__ == '__main__':
    main()

