#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Second probe: numeric per-plane statistics on the H13 gold sample to infer
plane order / channel roles (C/M/Y/K/W)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_layout as P

prn_path = sys.argv[1] if len(sys.argv) > 1 else \
    r'D:\Code\kkf\ripstudio\bin\bin\temp\data\1788919812455.prn'
prn = P.parse_prn(prn_path)
C = prn['nColorPlane']
W, H = prn['nWidth'], prn['nHeight']
print('W,H,C,BPL,dotbit =', W, H, C, prn['nBytesPerLine'], prn['dotbit_inferred'])

planes = [P.decode(prn, 'line', p) for p in range(C)]

# locate shape rows: union of all planes' nonzero coverage per row
def rowcov(p):
    out = []
    for y, r in enumerate(planes[p]):
        nz = sum(1 for v in r if v)
        out.append(nz)
    return out

print('row coverage summary (first/last nonzero row per plane):')
for p in range(C):
    rc = rowcov(p)
    nz_rows = [y for y, n in enumerate(rc) if n > 0]
    print(' plane%d: first=%s last=%s maxrowcov=%d' % (
        p, nz_rows[0] if nz_rows else None, nz_rows[-1] if nz_rows else None,
        max(rc) if rc else 0))

# Use union mask to find the two glyph bands (SNS on top, 10 below)
union = [0] * H
for p in range(C):
    for y in range(H):
        union[y] += sum(1 for v in planes[p][y] if v)
bands = []
inb = False
for y in range(H):
    if union[y] > 50 and not inb:
        st = y; inb = True
    elif union[y] <= 50 and inb:
        bands.append((st, y - 1)); inb = False
if inb:
    bands.append((st, H - 1))
print('ink row bands:', bands[:10])

# For each plane: mean dot value over each band's ink pixels, and over whole band
for p in range(C):
    line = []
    for (a, b) in bands[:4]:
        tot = 0
        cnt = 0
        inkpx = 0
        for y in range(a, b + 1):
            r = planes[p][y]
            for v in r:
                tot += v
                cnt += 1
                if v:
                    inkpx += 1
        line.append('band[%d-%d] mean=%.3f ink%%=%.3f' % (a, b, tot / max(1, cnt), inkpx / max(1, cnt)))
    print('plane%d: %s' % (p, ' | '.join(line)))

# Histograms per plane
for p in range(C):
    hist = [0, 0, 0, 0]
    for r in planes[p]:
        for v in r:
            hist[v] += 1
    tot = sum(hist)
    print('plane%d hist:' % p, ['%.4f' % (h / tot) for h in hist])
