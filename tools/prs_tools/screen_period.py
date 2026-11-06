#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Periodicity test v2: direct lag correlations of extracted u/D field + integer-formula verification."""
import os, sys, math, collections, json
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
import prn_canvas

ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
ROW0, COL0 = 640, 0
W = H = 384
COLOR = {'C': 0x00, 'K': 0x04, 'M': 0x12, 'Y': 0x11}
CTONES = [16*i for i in range(1, 16)]

def load(ch, tone):
    cands = [os.path.join(SAMPLES, f'probe_screen_probe_{ch}{tone}_a3dtf1390_m2.prn'),
             os.path.join(SAMPLES, f'probe_sweep_{ch}{tone}_a3dtf1390_m2.prn')]
    fn = next((c for c in cands if os.path.exists(c)), None)
    if fn is None: return None
    cvs, info = prn_canvas.decode_canvas(fn, vstep=8, verbose=False)
    cv = cvs.get(COLOR[ch])
    if cv is None: return None
    return [[cv[ROW0+y][COL0+x] for x in range(W)] for y in range(H)]

def corr(a, b):
    n = len(a)
    ma = sum(a)/n; mb = sum(b)/n
    sa = sum((v-ma)**2 for v in a); sb = sum((v-mb)**2 for v in b)
    if sa == 0 or sb == 0: return 0.0
    return sum((a[i]-ma)*(b[i]-mb) for i in range(n))/math.sqrt(sa*sb)

def main():
    mats = {}
    for t in CTONES + [255]:
        m = load('C', t)
        if m: mats[t] = m
    present = sorted(mats)
    # integer formula check: level = (3*v + D) >> 8, v=tone
    # per pixel: D interval intersect [level*256-3v, level*256-3v+255] (int, inclusive upper 255+...)
    empty = 0
    widths = collections.Counter()
    Dmid = [[0.0]*W for _ in range(H)]
    cand_counts = collections.Counter()
    for y in range(H):
        for x in range(W):
            lo, hi = -10**9, 10**9
            for t in present:
                v = t
                lev = mats[t][y][x]
                lo = max(lo, lev*256 - 3*v)
                hi = min(hi, lev*256 - 3*v + 255)
            if hi < lo:
                empty += 1
                Dmid[y][x] = -1
            else:
                widths[hi-lo] += 1
                Dmid[y][x] = (lo+hi)/2
                cand_counts[int(hi-lo)+1] += 1
    print(f'integer-formula (level=(3v+D)>>8): empty={empty} ({empty*100.0/(W*H):.3f}%)')
    print('D interval widths (int units, top):', widths.most_common(8))
    print('candidate counts:', cand_counts.most_common(8))

    # lag correlations on Dmid (use only valid)
    print('\n-- lag correlations of D field --')
    for lag in (1, 2, 4, 8, 16, 32, 48, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352):
        xs = [(Dmid[y][x], Dmid[y][x+lag]) for y in range(H) for x in range(W-lag)]
        a = [p[0] for p in xs]; b = [p[1] for p in xs]
        c = corr(a, b)
        ys = [(Dmid[y][x], Dmid[y+lag][x]) for y in range(H-lag) for x in range(W)]
        c2 = corr([p[0] for p in ys], [p[1] for p in ys])
        if lag in (1,2,4,8,16,32,64,128,192,256) or c > 0.05 or c2 > 0.05:
            print(f'  lag={lag:3d}: corr_x={c:+.4f} corr_y={c2:+.4f}')

    # 2D autocorr peak search (small)
    best = []
    for dy in range(0, 120, 4):
        for dx in range(-120, 121, 4):
            if dx == 0 and dy == 0: continue
            xs = [(Dmid[y][x], Dmid[y+dy][x+dx]) for y in range(0, H-dy) for x in range(0, W-abs(dx))]
            if len(xs) < 5000: continue
            c = corr([p[0] for p in xs], [p[1] for p in xs])
            best.append((c, dx, dy))
    best.sort(reverse=True)
    print('\n2D autocorr top 10:', [(round(c,4), dx, dy) for c,dx,dy in best[:10]])

    # cross-tone: D fields from M/Y/K probes (5 tones) compare to C field
    print('\n-- cross-channel: 5-tone u interval midpoints vs C --')
    for ch in ('M', 'Y', 'K'):
        m2 = {}
        for t in (64, 128, 192, 255):
            mm = load(ch, t)
            if mm: m2[t] = mm
        if len(m2) < 3: continue
        chmid = [[0.0]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                lo, hi = -10**9, 10**9
                for t, mm in m2.items():
                    lev = mm[y][x]
                    lo = max(lo, lev*256 - 3*t)
                    hi = min(hi, lev*256 - 3*t + 255)
                chmid[y][x] = (lo+hi)/2
        a = [Dmid[y][x] for y in range(H) for x in range(W) if Dmid[y][x] >= 0]
        b = [chmid[y][x] for y in range(H) for x in range(W) if Dmid[y][x] >= 0]
        print(f'  {ch} vs C: corr={corr(a,b):+.4f} mean_diff={sum(x-y for x,y in zip(a,b))/len(a):+.2f}')

if __name__ == '__main__':
    main()
