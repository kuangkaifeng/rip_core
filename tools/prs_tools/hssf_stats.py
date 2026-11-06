#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Decode HSSF 0x5555 PRN (MainTop->board) to per-plane 2-bit stats.
Header: 12*u32 (48B). Data: bpl * height * planes bytes, 2-bit packed.
Determine plane layout (plane-major vs line-major) empirically.
"""
import sys, os, struct

def parse_header(d):
    sig, xdpi, ydpi, bpl, h, w, paperw, planes = struct.unpack_from('<8I', d, 0)
    res = struct.unpack_from('<4I', d, 32)
    return dict(sig=sig, xdpi=xdpi, ydpi=ydpi, bpl=bpl, h=h, w=w, paperw=paperw, planes=planes, res=res, data_off=48)

def plane_stats(d, layout):
    hd = parse_header(d)
    bpl, height, planes = hd['bpl'], hd['h'], hd['planes']
    data = d[48:]
    per = []
    if layout == 'plane_major':
        for p in range(planes):
            chunk = data[p*bpl*height:(p+1)*bpl*height]
            per.append(dot_hist(chunk))
    elif layout == 'line_major':
        # interleave: line i: plane0..planeN each bpl bytes
        stride = bpl*planes
        for p in range(planes):
            hs = [0,0,0,0]
            for y in range(height):
                chunk = data[y*stride+p*bpl:(y+1)*stride+p*bpl]
                h2 = dot_hist(chunk); hs = [a+b for a,b in zip(hs,h2)]
            per.append(hs)
    return hd, per

def dot_hist(chunk):
    hs = [0,0,0,0]
    for b in chunk:
        hs[b >> 6] += 1
        hs[(b >> 4) & 3] += 1
        hs[(b >> 2) & 3] += 1
        hs[b & 3] += 1
    return hs

def main():
    for fn in sys.argv[1:]:
        d = open(fn, 'rb').read()
        hd = parse_header(d)
        print(f"=== {os.path.basename(fn)} size={len(d)} sig=0x{hd['sig']:04X} dpi={hd['xdpi']}x{hd['ydpi']} bpl={hd['bpl']} h={hd['h']} w={hd['w']} planes={hd['planes']} data={len(d)-48} expect={hd['bpl']*hd['h']*hd['planes']}")
        for layout in ('plane_major','line_major'):
            hd2, per = plane_stats(d, layout)
            parts = []
            for i, hs in enumerate(per):
                n = sum(hs)
                m = (hs[1]+2*hs[2]+3*hs[3])/n if n else 0
                parts.append(f'p{i}:{m:.2f}')
            print(f'  {layout}: ' + '  '.join(parts))

if __name__ == '__main__':
    main()
