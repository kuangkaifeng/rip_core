#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Determine whether the halftone threshold field D is indexed by absolute PAGE coords
or by content-relative coords, using the margin experiment (same input, shifted content).

Also: validate page-vs-thr_C using patch20 (100px, known CMYK values) at page coords.
"""
import os, sys, collections, importlib
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
os.environ['PRN_UNPACK'] = 'msb'
import prn_canvas
importlib.reload(prn_canvas)

ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
COLOR = {'C': 0x00, 'K': 0x04, 'M': 0x12, 'Y': 0x11}
PAGE_ROW0 = 640; W = 384; VSTEP = 8

def decode(fn, vstep=8):
    cvs, info = prn_canvas.decode_canvas(fn, vstep=vstep, verbose=False)
    return cvs, info

def bbox_cv(cv):
    rows = [y for y in range(len(cv)) if any(cv[y])]
    cols = [x for x in range(len(cv[0])) if any(cv[y][x] for y in rows)]
    return (min(rows), max(rows), min(cols), max(cols)) if rows else None

def main():
    base_fn = os.path.join(SAMPLES, 'a3dtf1390_cmyk_quad_100_m2.prn')
    marg_fn = os.path.join(SAMPLES, 'exp_a3dtf1390_margin_5_10_15_20.prn')
    cb, ib = decode(base_fn)
    cm, im = decode(marg_fn)
    for tag, cvs in (('base', cb), ('margin', cm)):
        for ch, code in COLOR.items():
            cv = cvs.get(code)
            if cv: print(f'{tag} {ch}: bbox={bbox_cv(cv)}')
    # find shift (dx,dy) maximizing pattern equality between base and margin for C channel
    b = cb.get(0x00); m = cm.get(0x00)
    if b is None or m is None:
        print('missing C'); return
    best = []
    H = min(len(b), len(m))
    for dy in range(-120, 121, 2):
        for dx in range(-120, 121, 2):
            match = tot = 0
            for y in range(200, min(1400, H-1)):
                my = y + dy
                if not (0 <= my < len(m)): continue
                rb = b[y]; rm = m[my]
                for x in range(0, 384, 2):
                    mx = x + dx
                    if not (0 <= mx < len(rm)): continue
                    vb, vm = rb[x], rm[mx]
                    # only compare where either has ink (flat patches)
                    tot += 1
                    if vb == vm: match += 1
            if tot:
                best.append((match/tot, dx, dy, tot))
    best.sort(reverse=True)
    print('top shifts (match, dx, dy):', [(round(r,4), dx, dy) for r, dx, dy, _ in best[:5]])

if __name__ == '__main__':
    main()
