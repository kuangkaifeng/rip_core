#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract exact 2-bit halftone threshold fields for all 4 inks from the 256-level
probe_scan<INK>### PRNs (mode2, 720x720, A3-DTF-1390).

Model (validated):
   level(v, x, y) = (v>=T1) + (v>=T2) + (v>=T3)      with per-pixel thresholds 1<=T1<=T2<=T3<=255
   equivalently level = (3*v + D) >> 8, D in [0,255], Tk = ceil((256*k - D)/3)
Raster->page geometry (A3 mode2, verified):
   block k rows at page_row = 79*k + 8*r  (VSTEP=8 page units = 90dpi vertical)
   content = 384 page rows x 384 page cols; per channel content top row differs
   (C/K start 640; M/Y start 644) -> detected from the t=255 scan.
   ESC/P2 2-bit data: 4 dots/byte, MSB pair = leftmost dot (verified with checker_1px).

Outputs:
   build/screen/screen_meta.json, build/screen/thr_<ink>.bin (384*384*3 B, [T1,T2,T3])
   reference/screen/ same + D_<ink>.bin (uint8) + extraction report
"""
import os, sys, json, struct, array, collections, importlib.util, time
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
OUT_REF = os.path.join(ROOT, 'reference', 'screen')
OUT_BUILD = os.path.join(ROOT, 'build', 'screen')
SIZE = 384
VSTEP = 8
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def scan_prn(P, fn, color):
    """Decode one PRN, return {page_row: row_values(384)} for given color code."""
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    pos = 0
    rows = {}
    for blk in job.blocks:
        if blk.advance is not None:
            pos += blk.advance
        for rec in blk.records:
            if rec.color != color or not rec.raw:
                continue
            for r in range(rec.m):
                page_row = pos + VSTEP*r
                chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                if len(chunk) < 96:
                    continue
                vals = []
                for b in chunk[:96]:
                    vals.extend(UNPACK[b])
                # last-wins / first-wins: keep existing if already present
                if page_row not in rows:
                    rows[page_row] = vals
                else:
                    old = rows[page_row]
                    # merge: 'both=0' expected; prefer nonzero
                    rows[page_row] = [o if o else v for o, v in zip(old, vals)]
    return rows

def extract_channel(ink):
    P = load_parser()
    code = COLOR[ink]
    t0 = time.time()
    # t=255 scan to find content top
    rows255 = scan_prn(P, os.path.join(SAMPLES, f'probe_scan_{ink}255_a3dtf1390_m2.prn'), code)
    nz = [r for r, v in rows255.items() if any(v)]
    if not nz:
        print(f'{ink}: no rows at t=255'); return None
    r0 = min(nz)
    print(f'{ink}: content top page row={r0}, rows with ink={len(nz)} (expect 384)')
    # inverse map page_row -> raster values for the 384 content rows
    # (verify one raster position per page row)
    page_rows = list(range(r0, r0+SIZE))
    row_vals = {}
    for pr in page_rows:
        if pr in rows255:
            row_vals[pr] = rows255[pr]
    print(f'{ink}: covered page rows {len(row_vals)} / {SIZE}')
    T1 = [[0]*SIZE for _ in range(SIZE)]
    T2 = [[0]*SIZE for _ in range(SIZE)]
    T3 = [[0]*SIZE for _ in range(SIZE)]
    for t in range(1, 256):
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}_a3dtf1390_m2.prn')
        if not os.path.exists(fn):
            continue
        rows = scan_prn(P, fn, code)
        for y, pr in enumerate(page_rows):
            vals = rows.get(pr)
            if not vals:
                continue
            T1y, T2y, T3y = T1[y], T2[y], T3[y]
            for x in range(SIZE):
                v = vals[x]
                if v:
                    if not T1y[x]: T1y[x] = t
                    if v >= 2 and not T2y[x]: T2y[x] = t
                    if v >= 3 and not T3y[x]: T3y[x] = t
        if t % 32 == 0:
            print(f'  {ink} t={t} ({time.time()-t0:.0f}s)', flush=True)
    # completeness / derive D
    miss = sum(1 for y in range(SIZE) for x in range(SIZE) if not T1[y][x])
    D = [[0]*SIZE for _ in range(SIZE)]
    amb = collections.Counter()
    for y in range(SIZE):
        for x in range(SIZE):
            t1, t2, t3 = T1[y][x], T2[y][x], T3[y][x]
            if not t1: continue
            cand = set(range(256-3*t1, 258-3*t1+1))
            if t2: cand &= set(range(512-3*t2, 514-3*t2+1))
            if t3: cand &= set(range(768-3*t3, 770-3*t3+1))
            cand = {c for c in cand if 0 <= c <= 255}
            amb[len(cand)] += 1
            if cand: D[y][x] = int(round(sum(cand)/len(cand)))
    print(f'{ink}: inked pixels={SIZE*SIZE-miss}, missing={miss}, D candidate sizes={amb.most_common(5)}')
    return dict(ink=ink, r0=r0, T1=T1, T2=T2, T3=T3, D=D, amb=dict(amb))

def write_bin(path, ch):
    data = bytearray()
    T1, T2, T3 = ch['T1'], ch['T2'], ch['T3']
    for y in range(SIZE):
        for x in range(SIZE):
            data.append(T1[y][x]); data.append(T2[y][x] if T2[y][x] <= 255 else 0); data.append(T3[y][x] if T3[y][x] <= 255 else 0)
    with open(path, 'wb') as f:
        f.write(data)

def main():
    os.makedirs(OUT_REF, exist_ok=True); os.makedirs(OUT_BUILD, exist_ok=True)
    channels = []
    for ink in ('C', 'M', 'Y', 'K'):
        ch = extract_channel(ink)
        if ch is None: continue
        channels.append(ch)
        write_bin(os.path.join(OUT_BUILD, f'thr_{ink}.bin'), ch)
        write_bin(os.path.join(OUT_REF, f'thr_{ink}.bin'), ch)
        with open(os.path.join(OUT_REF, f'D_{ink}.bin'), 'wb') as f:
            f.write(bytes(ch['D'][y][x] for y in range(SIZE) for x in range(SIZE)))
        ch['D'] = None; ch['T1'] = ch['T2'] = ch['T3'] = None  # free
    meta = dict(
        size=SIZE,
        engine_rule='level(v,x,y) = (v>=T1)+(v>=T2)+(v>=T3); file thr_<ink>.bin = size*size*3 bytes [T1,T2,T3] uint8 raster order y*size+x; 0 = never',
        data_layout='per pixel [T1,T2,T3] bytes; 0 means that transition never happens (only possible for T2/T3)',
        mode=dict(machine='A3-DTF-1390', prs='A3-DTF-1390.prs', modeId=2, dpi='720x720 (ESC(P) page unit 720/in)'),
        page_region=dict(pixel_origin_page_row_note='content top page row differs per ink; see content_top_page_row',
                         cols=0, size=SIZE),
        channels=[dict(ink=ch['ink'], file=f"thr_{ch['ink']}.bin", phaseX=0, phaseY=0,
                       content_top_page_row=ch['r0']) for ch in channels],
        source='probe_scan_<INK>###_a3dtf1390_m2.prn (256 levels each), T1 raster scan via analyzer',
        notes='Exact thresholds: sampled every ink value 0..255, transitions are exact (no interpolation). '
              'Physical column order: ESC/P2 2-bit MSB pair = leftmost dot (verified with checker_1px probe). '
              'Unknown extrapolation outside the 384x384 page region: see docs/color_pipeline.md §加网.')
    for base in (OUT_REF, OUT_BUILD):
        with open(os.path.join(base, 'screen_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
    print('saved build/screen + reference/screen')

if __name__ == '__main__':
    main()
