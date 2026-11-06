#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug: compare T1-bin-derived D against 16-tone-derived D intervals; test mapping alignments."""
import os, sys, array, collections, math
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
import prn_canvas

ROOT = r"D:\work\RIP核心分析"
BIN = os.path.join(ROOT, 'work', 'protocol', 'evidence', 'probe_scan_thresholds.bin')
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
SIZE = 384; W = 384; PAGE_ROW0 = 640
N = 449280

def load_bin():
    d = open(BIN, 'rb').read()
    return [array.array('H', d[i*N*2:(i+1)*N*2]) for i in range(3)]

def raster_index(blk, r): return (blk*90 + r)*W

def page_from_raster(blk, r):
    py = 79*blk + 8*r
    if PAGE_ROW0 <= py <= PAGE_ROW0 + SIZE - 1:
        return py - PAGE_ROW0
    return None

def build_page_t(choice):
    """choice: 'first' or 'last' nonzero in case of multiple positions for a page row."""
    T = [[None]*SIZE for _ in range(SIZE)]
    order = []
    for blk in range(13):
        for r in range(90):
            y = page_from_raster(blk, r)
            if y is None: continue
            order.append((blk, r, y))
    for blk, r, y in order:
        base = raster_index(blk, r)
        for x in range(W):
            t = (T[0][y][x] if False else None, )
            t1, t2, t3 = T1[base+x], T2[base+x], T3[base+x]
            if any((t1, t2, t3)):
                if T[y][x] is None:
                    T[y][x] = [t1, t2, t3]
                elif choice == 'last':
                    T[y][x] = [t1, t2, t3]
    return T

def obs_levels(tone):
    cands = [os.path.join(SAMPLES, f'probe_screen_probe_C{tone}_a3dtf1390_m2.prn'),
             os.path.join(SAMPLES, f'probe_sweep_C{tone}_a3dtf1390_m2.prn')]
    fn = next((c for c in cands if os.path.exists(c)), None)
    cvs, info = prn_canvas.decode_canvas(fn, vstep=8, verbose=False)
    cv = cvs[0]
    return [[cv[PAGE_ROW0+y][x] for x in range(SIZE)] for y in range(SIZE)]

T1, T2, T3 = load_bin()
print('T array ranges:', (min(T1), max(T1)), (min(T2), max(T2)), (min(T3), max(T3)))
# page y for raster row 80 (blk0): expect 0
print('blk0 row80 -> page y', page_from_raster(0,80))
# sample pixel page(0,0)
base = raster_index(0, 80)
print('page(0,0) thr:', T1[base], T2[base], T3[base])
obs64 = obs_levels(64)
for tone in (16, 32, 64, 96, 128):
    o = obs_levels(tone)
    print(f'  tone {tone}: obs level at (0,0)={o[0][0]}, (0,1)={o[0][1]}, (1,0)={o[1][0]}')
# derive D candidates
Tc = build_page_t('first')
miss = sum(1 for y in range(SIZE) for x in range(SIZE) if Tc[y][x] is None)
print('missing page thresholds:', miss)

def candD(t):
    if t is None or t[0] == 0: return set()
    cand = set(range(256-3*t[0], 258-3*t[0]+1))
    if t[1]: cand &= set(range(512-3*t[1], 514-3*t[1]+1))
    if t[2]: cand &= set(range(768-3*t[2], 770-3*t[2]+1))
    return {c for c in cand if 0 <= c <= 255}

# my earlier D interval from 16 tones
tones = [16*i for i in range(1,16)]
mats = {}
for t in tones:
    mats[t] = obs_levels(t)
Dmid = [[None]*SIZE for _ in range(SIZE)]
widths = collections.Counter()
mism = 0
for y in range(SIZE):
    for x in range(SIZE):
        lo, hi = -1e9, 1e9
        for t in tones:
            lev = mats[t][y][x]
            lo = max(lo, lev*256 - 3*t); hi = min(hi, lev*256 - 3*t + 255)
        Dmid[y][x] = (lo+hi)/2
        widths[hi-lo+1] += 1
print('16-tone D interval widths:', widths.most_common(4))

# compare
both = []
for y in range(SIZE):
    for x in range(SIZE):
        cd = candD(Tc[y][x])
        if not cd: continue
        d = sum(cd)/len(cd)
        both.append((Dmid[y][x], d))
print('samples:', len(both))
# correlation
ma = sum(p[0] for p in both)/len(both); mb = sum(p[1] for p in both)/len(both)
sa = math.sqrt(sum((p[0]-ma)**2 for p in both)); sb = math.sqrt(sum((p[1]-mb)**2 for p in both))
cc = sum((p[0]-ma)*(p[1]-mb) for p in both)/(sa*sb)
print(f'corr(16-tone D, bin D)={cc:.4f}  range16={min(p[0] for p in both):.1f}..{max(p[0] for p in both):.1f} rangebin={min(p[1] for p in both):.1f}..{max(p[1] for p in both):.1f}')
consistent = sum(1 for a, b in both if abs(a-b) <= 16)
print(f'within-16 agreement: {consistent*100.0/len(both):.2f}%')

# check level prediction using first mapping
def pred_level(tone, y, x):
    return int(bool(Tc[y][x][0]) and tone >= Tc[y][x][0]) + int(bool(Tc[y][x][1]) and tone >= Tc[y][x][1]) + int(bool(Tc[y][x][2]) and tone >= Tc[y][x][2])
tot = mism = 0
for tone in (64, 128):
    o = obs_levels(tone)
    for y in range(SIZE):
        for x in range(SIZE):
            tot += 1
            if pred_level(tone, y, x) != o[y][x]: mism += 1
print(f'direct mapping (first) mismatch {mism*100.0/tot:.2f}%')
