#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Precise double-array finder: locate runs of f64 starts of ramps (1/255 steps)."""
import sys, struct

def f64(d,o): return struct.unpack_from('<d', d, o)[0]

def find_ramp(d, i_target=0x3F70101010101010):
    # find byte pattern of 1/255
    pat = struct.pack('<d', 1.0/255.0)
    print('pattern of 1/255:', pat.hex(' '))
    hits = []
    i = 0
    while True:
        i = d.find(pat, i)
        if i < 0: break
        hits.append(i)
        i += 1
    print(f'hits of 1/255 pattern: {[hex(h) for h in hits]}')
    for h in hits:
        # walk backwards to find start: values decreasing by 1/255
        start = h
        k = 1
        while start-8 >= 0 and abs(f64(d,start-8) - k/255.0) < 1e-12:
            start -= 8; k += 1
        # walk forward count
        n = 0
        p = start
        while p+8 <= len(d) and abs(f64(d,p) - n/255.0) < 1e-12:
            n += 1; p += 8
        print(f'  ramp start=0x{start:X} count={n} (first=0 last={(n-1)/255:.6f})')
        print('   raw first 24 bytes:', d[start:start+24].hex(' '))

if __name__ == '__main__':
    fn = sys.argv[1] if len(sys.argv) > 1 else r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\A3-DTF-1390.prs"
    d = open(fn,'rb').read()
    find_ramp(d)
