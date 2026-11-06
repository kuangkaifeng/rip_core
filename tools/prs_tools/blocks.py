#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dump context around mode path blocks; search for dpi/pass-like values."""
import sys, struct, os

BIN = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin"
def load(fn): return open(fn, 'rb').read()

def u32(d,o): return int.from_bytes(d[o:o+4],'little')
def u16(d,o): return int.from_bytes(d[o:o+2],'little')
def i32(d,o): return int.from_bytes(d[o:o+4],'little',signed=True)

def dump_block(d, path_off, back=0x100, fwd=0x40):
    lo = max(0, path_off-back)
    print(f'--- context before path @0x{path_off:X} ---')
    for off in range(lo, path_off+fwd, 16):
        chunk = d[off:off+16]
        hexs = ' '.join(f'{b:02X}' for b in chunk)
        print(f'{off:06X}  {hexs:<48}')

def scan_region_for_dpi(d, lo, hi, targets=(360,720,1080,1200,1400,1440,1800,2160,2880,600,120)):
    print(f'scan 0x{lo:X}-0x{hi:X} for dpi/pass values')
    hits=[]
    for off in range(lo, hi-4, 4):
        v = u32(d, off)
        if v in targets:
            hits.append((off, v, 'u32'))
    for off, v, t in hits[:400]:
        print(f'  {off:06X} {t}={v}')
    return hits

if __name__ == '__main__':
    fn = sys.argv[1]
    d = load(fn)
    mode = sys.argv[2] if len(sys.argv) > 2 else 'ctx'
    if mode == 'ctx':
        for off in [int(x,0) for x in sys.argv[3:]]:
            dump_block(d, off)
    elif mode == 'hex':
        lo, hi = int(sys.argv[3],0), int(sys.argv[4],0)
        for off in range(lo, hi, 16):
            chunk = d[off:off+16]
            print(f'{off:06X}  ' + ' '.join(f'{b:02X}' for b in chunk))
