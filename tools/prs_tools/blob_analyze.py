#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze the opaque per-mode blobs in A3/H13 PRS: entropy, repetition, size factors,
possible threshold-matrix structure."""
import sys, struct, collections, math

FN = r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\A3-DTF-1390.prs"
d = open(FN, 'rb').read()

# record starts/ends derived from path offsets (A3):
# rec spans: [0x8034..0x109BC], [0x109BC..0x197C0], [0x197C0..0x224B4]
RECS = [(0x8034, 0x109BC), (0x109BC, 0x197C0), (0x197C0, 0x224B4)]
LUT_LEN = 8*256*8 + 7*12   # 16468
CONFIG = 96
PATHS = 2*(4*260)
MID = 88
TABLE = 116

def entropy(b):
    c = collections.Counter(b)
    n = len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

for i, (s, e) in enumerate(RECS):
    span = e - s
    tail = LUT_LEN + CONFIG + PATHS + MID
    blob_len = span - tail
    if i == 0:
        blob = d[s:s+blob_len]
    print(f'record{i}: span={span} blob={blob_len} entropy={entropy(d[s:s+blob_len]):.2f}')
    print(f'  first 64B: {d[s:s+64].hex(" ")}')
    print(f'  last 128B of blob: {d[s+blob_len-128:s+blob_len].hex(" ")}')
    print(f'  byte hist top: {collections.Counter(d[s:s+blob_len]).most_common(8)}')
    # look for float/double ramps inside blob
    print()

# Search for possible float ramps in whole file (f32 in [0,1] sequences)
def find_f32_ramps(d, lo=0, hi=None, minrun=32):
    hi = hi or len(d)
    res = []
    o = lo
    while o + 4*minrun <= hi:
        vals = []
        p = o
        while p+4 <= hi:
            v = struct.unpack_from('<f', d, p)[0]
            if 0.0 <= v <= 1.0001:
                vals.append(v); p += 4
            else:
                break
        if len(vals) >= minrun:
            res.append((o, len(vals), vals[:6], vals[-3:]))
            o = p
        else:
            o += 4
    return res

print('=== f32 runs >=32 in whole A3 prs (first 20) ===')
for r in find_f32_ramps(d)[:20]:
    print(f'  @0x{r[0]:X} n={r[1]} first={r[2]} last={r[3]}')
