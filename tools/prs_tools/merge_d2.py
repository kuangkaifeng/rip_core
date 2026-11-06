#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Per-channel D-field constraints merge (mode2).
Test A: D indexed by absolute page coords (py=page row, px=page col)
Test B: D shifted by per-channel row offset (M/Y content starts 644 vs C/K 640) -> align content tops.
"""
import os, sys, collections, json
from PIL import Image
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
import prn_canvas

ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
INPUTS = os.path.join(ROOT, 'reference', 'inputs')
COLOR = {'C': 0x00, 'K': 0x04, 'M': 0x12, 'Y': 0x11}
CHIDX = {'C': 0, 'M': 1, 'Y': 2, 'K': 3}
VSTEP = 8

def decode(fn):
    cvs, info = prn_canvas.decode_canvas(fn, vstep=VSTEP, verbose=False)
    return cvs

def bbox(cv):
    rows = [y for y in range(len(cv)) if any(cv[y])]
    return (min(rows), max(rows)) if rows else None

def tiff_ink(fn):
    im = Image.open(fn); px = im.load(); W, H = im.size
    return [[px[x, y] for x in range(W)] for y in range(H)], W, H

def collect_channel(ch):
    """Return list of (content_r0, Wdots, inkmatrix, cv, imgw, imgh)."""
    out = []
    files = []
    for t in range(16, 241, 16):
        files.append((f'Csweep{t}', os.path.join(SAMPLES, f'probe_sweep_{ch}{t}_a3dtf1390_m2.prn'),
                      os.path.join(INPUTS, f'cmyk_probe_{ch}{t}_64.tif')))
    for t in (0, 64, 128, 192, 255):
        files.append((f'{ch}{t}', os.path.join(SAMPLES, f'probe_screen_probe_{ch}{t}_a3dtf1390_m2.prn'),
                      os.path.join(INPUTS, f'cmyk_probe_{ch}{t}_64.tif')))
    for name in ('cmyk_ramp16_160', 'cmyk_patch20_100', 'cmyk_full4_100', 'cmyk_full_100'):
        files.append((name, os.path.join(SAMPLES, f'probe_screen_{name}_a3dtf1390_m2.prn'),
                      os.path.join(INPUTS, f'{name}.tif')))
    for name, prn, tif in files:
        if not (os.path.exists(prn) and os.path.exists(tif)):
            continue
        cvs = decode(prn)
        cv = cvs.get(COLOR[ch])
        if cv is None:
            continue
        bb = bbox(cv)
        if not bb:
            continue
        ink, W, H = tiff_ink(tif)
        # verify this channel has any nonzero ink
        if not any(ink[iy][ix][CHIDX[ch]] for iy in range(H) for ix in range(W)):
            continue
        out.append((name, bb[0], len(cv[0]), ink, cv, W, H))
    return out

def build(align_content=True):
    fields = {}
    for ch in COLOR:
        cons = {}
        for name, r0, Wdots, ink, cv, W, H in collect_channel(ch):
            for iy in range(H):
                for ix in range(W):
                    v = ink[iy][ix][CHIDX[ch]]
                    if not v: continue
                    for dy in range(6):
                        py = r0 + 6*iy + dy
                        for dx in range(6):
                            pxx = 6*ix + dx
                            if pxx >= Wdots: continue
                            L = cv[py][pxx]
                            lo = L*256 - 3*v; hi = lo + 255
                            key = (py - (r0 if align_content else 0), pxx)
                            cur = cons.get(key)
                            if cur is None: cons[key] = [lo, hi]
                            else:
                                cur[0] = max(cur[0], lo); cur[1] = min(cur[1], hi)
        fields[ch] = cons
    return fields

def report(fields, label):
    print(f'\n=== {label} ===')
    for ch, cons in fields.items():
        empt = sum(1 for lo, hi in cons.values() if hi < lo)
        widths = collections.Counter(hi-lo+1 for lo, hi in cons.values() if hi >= lo)
        print(f'  {ch}: pixels={len(cons)} empty={empt} ({empt*100.0/max(1,len(cons)):.2f}%) widths={widths.most_common(6)}')

if __name__ == '__main__':
    for align in (False, True):
        fields = build(align_content=align)
        report(fields, f'per-channel merge, align_content={align}')
        if align:
            out = os.path.join(ROOT, 'reference', 'screen')
            os.makedirs(out, exist_ok=True)
            js = {}
            for ch, cons in fields.items():
                empt = sum(1 for lo, hi in cons.values() if hi < lo)
                widths = collections.Counter(hi-lo+1 for lo, hi in cons.values() if hi >= lo)
                js[ch] = dict(pixels=len(cons), empty=empt, widths={str(k): v for k, v in widths.most_common(20)})
            with open(os.path.join(out, 'D_constraints_per_channel.json'), 'w', encoding='utf-8') as f:
                json.dump(js, f, indent=1)
            print('saved -> reference/screen/D_constraints_per_channel.json')
