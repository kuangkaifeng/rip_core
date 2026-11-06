#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate extracted threshold fields against probe PRNs (all 4 inks),
compute cross-channel D correlations in content coordinates,
and test whether D is page-absolute vs content-relative using the margin experiment.
"""
import os, sys, json, collections, math
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
os.environ['PRN_UNPACK'] = 'msb'
import prn_canvas
import importlib
importlib.reload(prn_canvas)

ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
SCREEN = os.path.join(ROOT, 'reference', 'screen')
SIZE = 384; VSTEP = 8
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}

def load_thr(ink):
    d = open(os.path.join(SCREEN, f'thr_{ink}.bin'), 'rb').read()
    assert len(d) == SIZE*SIZE*3, len(d)
    T = [[(d[(y*SIZE+x)*3], d[(y*SIZE+x)*3+1], d[(y*SIZE+x)*3+2]) for x in range(SIZE)] for y in range(SIZE)]
    return T

def load_D(ink):
    d = open(os.path.join(SCREEN, f'D_{ink}.bin'), 'rb').read()
    return [[d[y*SIZE+x] for x in range(SIZE)] for y in range(SIZE)]

def obs_levels(ink, tone):
    fn = os.path.join(SAMPLES, f'probe_scan_{ink}{tone:03d}_a3dtf1390_m2.prn')
    if not os.path.exists(fn):
        # fallback older names
        cands = [os.path.join(SAMPLES, f'probe_screen_probe_{ink}{tone}_a3dtf1390_m2.prn'),
                 os.path.join(SAMPLES, f'probe_sweep_{ink}{tone}_a3dtf1390_m2.prn')]
        fn = next((c for c in cands if os.path.exists(c)), None)
    if fn is None: return None
    cvs, info = prn_canvas.decode_canvas(fn, vstep=VSTEP, verbose=False)
    cv = cvs.get(COLOR[ink])
    if cv is None: return None
    top = TOP[ink]
    return [[cv[top+y][x] for x in range(SIZE)] for y in range(SIZE)]

def main():
    mats = {ink: load_thr(ink) for ink in COLOR}
    print('=== validation: predicted vs observed probe PRN levels ===')
    worst = 1.0
    for ink in COLOR:
        T = mats[ink]
        for tone in (16, 64, 128, 192, 240, 255):
            o = obs_levels(ink, tone)
            if o is None: continue
            mism = 0; tot = 0
            for y in range(SIZE):
                for x in range(SIZE):
                    t1, t2, t3 = T[y][x]
                    pred = (1 if t1 and tone >= t1 else 0) + (1 if t2 and tone >= t2 else 0) + (1 if t3 and tone >= t3 else 0)
                    tot += 1
                    if pred != o[y][x]: mism += 1
            acc = (tot-mism)*100.0/tot
            worst = min(worst, acc)
            print(f'  {ink} tone {tone:3d}: match={acc:.4f}%')
    print(f'worst match: {worst:.4f}%')

    # cross-channel D correlation in content coordinates
    print('\n=== cross-channel D-field correlation (content coords) ===')
    Ds = {ink: load_D(ink) for ink in COLOR}
    for ink in ('M', 'Y', 'K'):
        a = [Ds['C'][y][x] for y in range(SIZE) for x in range(SIZE)]
        b = [Ds[ink][y][x] for y in range(SIZE) for x in range(SIZE)]
        ma = sum(a)/len(a); mb = sum(b)/len(b)
        sa = math.sqrt(sum((v-ma)**2 for v in a)); sb = math.sqrt(sum((v-mb)**2 for v in b))
        c = sum((a[i]-ma)*(b[i]-mb) for i in range(len(a)))/(sa*sb)
        # also page-coordinate compare: shift M/Y by +4 rows
        if ink in ('M', 'Y'):
            a2 = [Ds['C'][y][x] for y in range(SIZE-4) for x in range(SIZE)]
            b2 = [Ds[ink][y+4][x] for y in range(SIZE-4) for x in range(SIZE)]
            ma2 = sum(a2)/len(a2); mb2 = sum(b2)/len(b2)
            sa2 = math.sqrt(sum((v-ma2)**2 for v in a2)); sb2 = math.sqrt(sum((v-mb2)**2 for v in b2))
            c2 = sum((a2[i]-ma2)*(b2[i]-mb2) for i in range(len(a2)))/(sa2*sb2)
            print(f'  C vs {ink}: content-coord corr={c:+.4f}; page-coord(shift {TOP[ink]-TOP["C"]}) corr={c2:+.4f}')
        else:
            print(f'  C vs {ink}: content-coord corr={c:+.4f}')

    # margin experiment: page-absolute vs content-relative
    print('\n=== margin experiment (page-absolute vs content-relative) ===')
    base_fn = os.path.join(SAMPLES, 'a3dtf1390_cmyk_quad_100_m2.prn')
    marg_fn = os.path.join(SAMPLES, 'exp_a3dtf1390_margin_5_10_15_20.prn')
    cb, _ = prn_canvas.decode_canvas(base_fn, vstep=VSTEP, verbose=False)
    cm, _ = prn_canvas.decode_canvas(marg_fn, vstep=VSTEP, verbose=False)
    for code in (0x00, 0x04, 0x11, 0x12):
        b = cb.get(code); m = cm.get(code)
        if b is None or m is None: continue
        # bboxes
        rb = [y for y in range(len(b)) if any(b[y])]
        rm = [y for y in range(len(m)) if any(m[y])]
        if not rb or not rm: continue
        by0, my0 = min(rb), min(rm)
        bc = [x for x in range(len(b[0])) if any(b[y][x] for y in rb)]
        mc = [x for x in range(len(m[0])) if any(m[y][x] for y in rm)]
        bx0, mx0 = min(bc), min(mc)
        dy, dx = my0-by0, mx0-bx0
        # compare patterns: page coords
        same_page = tot = 0
        same_content = tot2 = 0
        for y in range(max(by0, my0), min(max(rb), max(rm))+1):
            for x in range(max(bx0, mx0), min(max(bc), max(mc))+1):
                vb = b[y][x]; vm = m[y][x]
                tot += 1; same_page += (vb == vm)
                # content coords: margin content pixel shifts by (dy,dx)
                yc = y+dy; xc = x+dx
                if 0 <= yc < len(m) and 0 <= xc < len(m[0]):
                    tot2 += 1; same_content += (vm == m[yc][xc] if False else (vb == m[y+dy][x+dx] and b[y][x] == m[y+dy][x+dx]))
        print(f'  code 0x{code:02X}: bbox shift dy={dy} dx={dx}; page-coord match={same_page*100.0/max(1,tot):.2f}%')
    # simpler: determine shift by maximizing page-coord equality for one color
    for code in (0x00, 0x04):
        b = cb.get(code); m = cm.get(code)
        if not b or not m: continue
        best = (0,0,0)
        for ddy in range(-80, 81, 4):
            for ddx in range(-80, 81, 4):
                mt = tt = 0
                for y in range(700, 1200, 3):
                    for x in range(0, 384, 3):
                        ym = y+ddy; xm = x+ddx
                        if 0 <= ym < len(m) and 0 <= xm < len(m[0]):
                            tt += 1
                            if b[y][x] == m[ym][xm]: mt += 1
                if tt and mt/tt > best[0]:
                    best = (mt/tt, ddy, ddx)
        print(f'  code 0x{code:02X}: best page-coord match={best[0]*100:.2f}% at shift ({best[1]},{best[2]})')

if __name__ == '__main__':
    main()
