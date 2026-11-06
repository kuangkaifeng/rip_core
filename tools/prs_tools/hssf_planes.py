#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Decode HSSF payload line-major: line y = plane0[bpl] plane1[bpl] ... ; each byte = 4 dots 2-bit MSB-first.
Print per-plane mean dot level and histogram for flat-color PRNs."""
import sys, os, struct

def hdr(d):
    return struct.unpack_from('<8I', d, 0) + struct.unpack_from('<4I', d, 32)

def stats(fn):
    d = open(fn, 'rb').read()
    sig, xdpi, ydpi, bpl, h, w, paperw, planes, r0, r1, r2, r3 = hdr(d)
    data = d[48:]
    line = bpl*planes
    out = []
    hist = [[0,0,0,0] for _ in range(planes)]
    for y in range(h):
        off = y*line
        for p in range(planes):
            chunk = data[off+p*bpl: off+(p+1)*bpl]
            hs = hist[p]
            for b in chunk:
                hs[b >> 6] += 1
                hs[(b >> 4) & 3] += 1
                hs[(b >> 2) & 3] += 1
                hs[b & 3] += 1
    for p in range(planes):
        hs = hist[p]
        n = sum(hs)
        m = (hs[1]+2*hs[2]+3*hs[3])/n if n else 0
        cov = (hs[1]+hs[2]+hs[3])/n if n else 0
        out.append((m, cov, hs))
    return dict(file=os.path.basename(fn), sig=sig, dpi=(xdpi, ydpi), bpl=bpl, h=h, w=w,
                planes=planes, res=(r0,r1,r2,r3), stats=out)

def main():
    for fn in sys.argv[1:]:
        r = stats(fn)
        parts = []
        for p, (m, cov, hs) in enumerate(r['stats']):
            parts.append(f"p{p}:mean={m:.3f},cov={cov:.3f},hist={hs}")
        print(f"{r['file']:42s} dpi={r['dpi']} planes={r['planes']}")
        for s in parts:
            print('   ', s)

if __name__ == '__main__':
    main()
