#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""1) Check exact relation between channel D fields (C vs M/Y/K).
2) Clean coordinate-index test: compare base vs margin PRN (same input image, content
   horizontally shifted by margin) at CONTENT-relative coords. ~100% => content-relative;
   random => page-absolute.
"""
import os, sys, collections, math
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
os.environ['PRN_UNPACK'] = 'msb'
import prn_canvas

ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
SCREEN = os.path.join(ROOT, 'reference', 'screen')
SIZE = 384; VSTEP = 8
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}

def load_D(ink):
    d = open(os.path.join(SCREEN, f'D_{ink}.bin'), 'rb').read()
    return [[d[y*SIZE+x] for x in range(SIZE)] for y in range(SIZE)]

def main():
    D = {ink: load_D(ink) for ink in COLOR}
    print('=== D field relations (content coords) ===')
    # candidates: D_M = a + b*D_C
    for ink in ('M', 'Y', 'K'):
        pairs = [(D['C'][y][x], D[ink][y][x]) for y in range(SIZE) for x in range(SIZE)]
        diffs = collections.Counter((b - a) % 256 for a, b in pairs)
        sums = collections.Counter((a + b) for a, b in pairs)
        same = sum(1 for a, b in pairs if a == b)
        inv = sum(1 for a, b in pairs if (a + b) == 255)
        print(f'  C vs {ink}: same={same*100.0/len(pairs):.2f}%  complement(255-a)={inv*100.0/len(pairs):.2f}%')
        print(f'    top diff mod256: {diffs.most_common(5)}')
    # check M = 255-C exactly where both known
    exact = sum(1 for y in range(SIZE) for x in range(SIZE) if D['M'][y][x] == 255 - D['C'][y][x])
    print(f'  M == 255-C exactly: {exact*100.0/(SIZE*SIZE):.2f}%')

    print('\n=== coordinate indexing: base vs margin (content-relative) ===')
    cb, _ = prn_canvas.decode_canvas(os.path.join(SAMPLES, 'a3dtf1390_cmyk_quad_100_m2.prn'), vstep=VSTEP, verbose=False)
    cm, _ = prn_canvas.decode_canvas(os.path.join(SAMPLES, 'exp_a3dtf1390_margin_5_10_15_20.prn'), vstep=VSTEP, verbose=False)
    # content bboxes
    def bbox(cv):
        rows = [y for y in range(len(cv)) if any(cv[y])]
        if not rows: return None
        cols = [x for x in range(len(cv[0])) if any(cv[y][x] for y in rows)]
        return min(rows), max(rows), min(cols), max(cols)
    for code in COLOR.values():
        b = cb.get(code); m = cm.get(code)
        if not b or not m: continue
        bb, bm = bbox(b), bbox(m)
        # content width = 600 dots for 100px input
        ch = COLOR_BY = None
        # try content-relative alignment: base content origin (bb row min, col min),
        # margin origin (bm row min, col min). Compare same content pixel.
        tot = same = 0
        for y in range(600):
            by = bb[0] + y
            my = bm[0] + y
            if by > bb[1] or my > bm[1]: break
            for x in range(600):
                bx = bb[2] + x
                mx = bm[2] + x
                if bx > bb[3] or mx > bm[3]: break
                tot += 1
                if b[by][bx] == m[my][mx]: same += 1
        print(f'  code 0x{code:02X}: content-relative match={same*100.0/max(1,tot):.2f}% (tot={tot})'
              f' base bbox={bb} margin bbox={bm}')

if __name__ == '__main__':
    main()
