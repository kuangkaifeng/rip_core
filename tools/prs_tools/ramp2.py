#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze ramp arrays precisely: start at first 1/255 double, check backward 0.0, forward length, gaps."""
import sys, struct

def f64(d,o): return struct.unpack_from('<d', d, o)[0]

FN = r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\A3-DTF-1390.prs"
d = open(FN,'rb').read()

pat = struct.pack('<d', 1.0/255.0)
starts = []
i = 0
while True:
    i = d.find(pat, i)
    if i < 0: break
    starts.append(i); i += 1

print(f'{len(starts)} ramp starts found')
prev_end = None
for h in starts:
    back = f64(d, h-8) if h >= 8 else None
    # forward count
    n = 0
    p = h
    while p+8 <= len(d) and abs(f64(d, p) - (n+1)/255.0) < 1e-12:
        n += 1; p += 8
    start = h - 8 if (back is not None and abs(back) < 1e-12) else h
    print(f'start=0x{start:06X} back8={back:.1f} len={n+1 if abs(back)<1e-12 else n} end=0x{p:06X} gap_to_prev={None if prev_end is None else start-prev_end}')
    # last values
    print('   last vals:', [f'{f64(d,p-8*k):.6f}' for k in range(1,4)])
    prev_end = p

