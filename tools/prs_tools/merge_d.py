#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Multi-job D-field constraint merging.

Jobs with KNOWN CMYK ink per image pixel (CMYK TIFF inputs, mode2 no-CC => device ink = input):
  cmyk_probe/C sweeps (64x64), cmyk_ramp16_160.tif, cmyk_patch20_100.tif, cmyk_full4/full
For each observed level L at device dot (page_row,page_col) with ink v:
  D satisfies: L*256 - 3v <= D <= L*256 - 3v + 255
Merge all constraints at same page coordinate; test consistency (empty intervals), width.
"""
import os, sys, collections, json
from PIL import Image
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
import prn_canvas

ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
INPUTS = os.path.join(ROOT, 'reference', 'inputs')
COLOR = {'C': 0x00, 'K': 0x04, 'M': 0x12, 'Y': 0x11}
CH_BY_COLOR = {v: k for k, v in COLOR.items()}
VSTEP = 8

def content_page_rows(info):
    pass

def decode_prn(fn, vstep=VSTEP):
    cvs, info = prn_canvas.decode_canvas(fn, vstep=vstep, verbose=False)
    return cvs, info

def find_content_bbox(cvs):
    rows = set(); cols = 0
    for cv in cvs.values():
        H = len(cv); W = len(cv[0]) if H else 0
        for y in range(H):
            if any(cv[y]): rows.add(y)
        cols = max(cols, W)
    if not rows: return None
    return min(rows), max(rows), cols

def tiff_ink(fn):
    im = Image.open(fn)
    if im.mode != 'CMYK':
        raise ValueError(f'{fn}: not CMYK ({im.mode})')
    W, H = im.size
    px = im.load()
    return [[px[x, y] for x in range(W)] for y in range(H)], W, H

def main():
    jobs = []  # (name, prn, tiff, content_page_row0)
    # 64x64 probes (C sweep tones; also M/Y/K base probes)
    for t in (64, 128, 192, 255):
        for ch in ('C', 'M', 'Y', 'K'):
            cands = [os.path.join(SAMPLES, f'probe_screen_probe_{ch}{t}_a3dtf1390_m2.prn')]
            if os.path.exists(cands[0]):
                jobs.append((f'{ch}{t}', cands[0], os.path.join(INPUTS, f'cmyk_probe_{ch}{t}_64.tif')))
    for t in range(16, 241, 16):
        fn = os.path.join(SAMPLES, f'probe_sweep_C{t}_a3dtf1390_m2.prn')
        tf = os.path.join(INPUTS, f'cmyk_probe_C{t}_64.tif')
        if os.path.exists(fn) and os.path.exists(tf):
            jobs.append((f'Csweep{t}', fn, tf))
    # 100px / 160px CMYK images
    for name in ('cmyk_ramp16_160', 'cmyk_patch20_100', 'cmyk_full4_100', 'cmyk_full_100'):
        fn = os.path.join(SAMPLES, f'probe_screen_{name}_a3dtf1390_m2.prn')
        tf = os.path.join(INPUTS, f'{name}.tif')
        if os.path.exists(fn) and os.path.exists(tf):
            jobs.append((name, fn, tf))
    print(f'{len(jobs)} jobs')

    # constraints: dict (page_row,page_col) -> [lo,hi]
    cons = {}
    unmatched = 0
    for name, prn, tif in jobs:
        cvs, info = decode_prn(prn)
        bbox = find_content_bbox(cvs)
        if bbox is None:
            print(f'{name}: empty'); continue
        r0, r1, Wdots = bbox
        ink, Wimg, Himg = tiff_ink(tif)
        # content height check: expect 6*Himg
        exp_h = 6*Himg
        got_h = r1 - r0 + 1
        print(f'{name}: content rows {r0}..{r1} (h={got_h}, expected {exp_h}), Wdots={Wdots} img={Wimg}x{Himg}')
        if got_h != exp_h:
            unmatched += 1
        for ch, color in COLOR.items():
            cv = cvs.get(color)
            if cv is None: continue
            for iy in range(Himg):
                for ix in range(Wimg):
                    v = ink[iy][ix][{'C':0,'M':1,'Y':2,'K':3}[ch]]
                    if v == 0:
                        continue
                    for dy in range(6):
                        py = r0 + 6*iy + dy
                        for dx in range(6):
                            px_ = 6*ix + dx
                            if px_ >= Wdots: continue
                            L = cv[py][px_]
                            lo = L*256 - 3*v
                            hi = lo + 255
                            key = (py, px_)
                            cur = cons.get(key)
                            if cur is None:
                                cons[key] = [lo, hi]
                            else:
                                cur[0] = max(cur[0], lo)
                                cur[1] = min(cur[1], hi)
    print(f'constraints at {len(cons)} page pixels')
    empties = 0
    widths = collections.Counter()
    for k, (lo, hi) in cons.items():
        if hi < lo:
            empties += 1
        else:
            widths[hi-lo+1] += 1
    print(f'empty={empties} ({empties*100.0/max(1,len(cons)):.3f}%)')
    print('candidate counts:', widths.most_common(10))
    # save constraints
    out = os.path.join(ROOT, 'reference', 'screen')
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'D_constraints.json'), 'w', encoding='utf-8') as f:
        json.dump({'count': len(cons), 'empty': empties,
                   'widths': {str(k): v for k, v in widths.most_common(20)},
                   'sample': {f'{y},{x}': cons[(y, x)] for (y, x) in list(cons)[:1000]}},
                  f, indent=1)
    print('saved -> reference/screen/D_constraints.json')

if __name__ == '__main__':
    main()
