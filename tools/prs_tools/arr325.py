#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze 325-double arrays + structure around mode regions in A3 prs."""
import sys, struct

FN = r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\A3-DTF-1390.prs"
d = open(FN, 'rb').read()

def f64(o): return struct.unpack_from('<d', d, o)[0]
def u32(o): return int.from_bytes(d[o:o+4], 'little')
def i32(o): return int.from_bytes(d[o:o+4], 'little', signed=True)

def analyze(base, n=325):
    vals = [f64(base + 8*i) for i in range(n)]
    print(f'=== array @0x{base:X} n={n} ===')
    print('  idx0-3:', vals[:4])
    # check formula max(0,(i-4))/255
    ok = all(abs(v - max(0.0, (i-4))/255.0) < 1e-9 for i, v in enumerate(vals[:300]))
    print('  formula max(0,(i-4))/255 holds for i<300:', ok)
    print('  vals[76:96]:', [f'{v:.6f}' for v in vals[76:96]])
    print('  vals[296:325]:', [f'{v:.6f}' for v in vals[296:325]])
    # find where deviations from ramp start
    for i, v in enumerate(vals):
        if abs(v - max(0.0, (i-4))/255.0) > 1e-9:
            print(f'  first deviation at i={i}: v={v:.9f} ramp={max(0.0,(i-4))/255.0:.9f}')
            break
    else:
        print('  whole array follows ramp')

def diff_arrays(a, b, n=325):
    va = [f64(a+8*i) for i in range(n)]
    vb = [f64(b+8*i) for i in range(n)]
    diffs = [(i, va[i]-vb[i]) for i in range(n) if abs(va[i]-vb[i]) > 1e-9]
    print(f'arrays 0x{a:X} vs 0x{b:X}: {len(diffs)} differing elems; first 10: {diffs[:10]}')

if __name__ == '__main__':
    for base in (0xD090, 0xE0A8, 0xF0C0, 0x15E18, 0x16E30, 0x17E48, 0x1E340, 0x1F358, 0x20370):
        analyze(base)
    print()
    diff_arrays(0xD090, 0xE0A8)
    diff_arrays(0xD090, 0x15E18)
    diff_arrays(0xD090, 0x1E340)
    # what is 0x7D10 run (2482 doubles)?
    print('=== 0x7D10 doubles every 1 until nonzero ===')
    i = 0
    while i < 2482 and f64(0x7D10 + 8*i) == 0.0:
        i += 1
    print('first nonzero at i=', i, 'value=', f64(0x7D10+8*i) if i < 2482 else None)
    print('vals around:', [f'{f64(0x7D10+8*j):.6f}' for j in range(max(0,i-2), min(2482,i+10))])
