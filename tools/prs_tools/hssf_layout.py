#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze HSSF payload layout: per-position-in-line byte histograms."""
import sys, os, struct, collections

def parse_header(d):
    sig, xdpi, ydpi, bpl, h, w, paperw, planes = struct.unpack_from('<8I', d, 0)
    res = struct.unpack_from('<4I', d, 32)
    return dict(sig=sig, xdpi=xdpi, ydpi=ydpi, bpl=bpl, h=h, w=w, paperw=paperw, planes=planes, res=res)

def main(fn):
    d = open(fn, 'rb').read()
    hd = parse_header(d)
    data = d[48:]
    bpl, h, planes = hd['bpl'], hd['h'], hd['planes']
    print(f'{os.path.basename(fn)}: bpl={bpl} h={h} planes={planes} data={len(data)}')
    # splits: 600*760
    line = len(data)//h
    print(f'  bytes/line={line} (bpl*planes={bpl*planes})')
    # per plane segment within a line
    for p in range(planes):
        seg = b''
        for y in range(0, h, 50):
            seg += data[y*line + p*bpl: y*line + (p+1)*bpl]
        c = collections.Counter(seg)
        print(f'  plane{p} bytes@{p*bpl}: hist top {c.most_common(5)}')
    # also try: 5 bytes interleaved per pixel?
    # print first 3 lines raw hex (first 64 bytes each)
    for y in (0, 1, 299):
        print(f'  line{y}: {data[y*line:y*line+64].hex(" ")}')
    # check 0xff/0xAA patterns positions
    c = collections.Counter(data)
    print('  whole data top:', c.most_common(8))

if __name__ == '__main__':
    for fn in sys.argv[1:]:
        main(fn)
