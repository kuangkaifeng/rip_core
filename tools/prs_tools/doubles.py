#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze per-mode blocks in .prs: find 8-byte double LUT sequences ending near path blocks."""
import sys, struct, os

def u32(d,o): return int.from_bytes(d[o:o+4],'little')
def f64(d,o): return struct.unpack_from('<d', d, o)[0]
def f32(d,o): return struct.unpack_from('<f', d, o)[0]

def find_double_runs(d, lo, hi):
    """find runs of >=8 consecutive valid doubles (monotone non-decreasing, 0..1.0001) aligned at end"""
    runs=[]
    o=lo
    while o+8<=hi:
        # try start a run
        vals=[]
        p=o
        while p+8<=hi:
            v=f64(d,p)
            if -0.001 <= v <= 1.001 and v==v:
                vals.append((p,v)); p+=8
            else:
                break
        if len(vals)>=8:
            runs.append(vals)
            o=p
        else:
            o+=8
    return runs

def fmt_vals(vals, n=8):
    s=[f'{v:.6f}' for _,v in vals[:n]]
    return '[' + ', '.join(s) + (', ...]' if len(vals)>n else ']')

if __name__=='__main__':
    fn=sys.argv[1]
    d=open(fn,'rb').read()
    print(f'{os.path.basename(fn)} size=0x{len(d):X}')
    runs=find_double_runs(d, 0, len(d))
    print(f'{len(runs)} double runs')
    for vals in runs:
        s,e=vals[0][0], vals[-1][0]
        print(f'  run @0x{s:X}..0x{e+8:X} n={len(vals)} first={fmt_vals(vals)} last={fmt_vals(vals[-8:],8)}')
