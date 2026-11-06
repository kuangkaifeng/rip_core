#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tile (1024x1024) symmetry analysis using the full-tile binary mask from C64_720 probe.
Level at v=64 is binary [D>=64]. Test: mirror/transpose/rotation/quadrant relations.
Also check exact tile period with finer shifts to confirm 1024.
"""
import os, sys, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
ROOT = r"D:\work\RIP核心分析"
FN = os.path.join(ROOT, 'reference', 'prn_samples', 'probe_scan_C64_720_a3dtf1390_m2.prn')
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]
P_TILE = 1024

def decode_rows(fn, code=0x00, vstep=8):
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    pos = 0; rows = {}; W = 0
    for blk in job.blocks:
        if blk.advance is not None: pos += blk.advance
        for rec in blk.records:
            if rec.color != code or not rec.raw: continue
            W = max(W, rec.n*4)
            for r in range(rec.m):
                pr = pos + vstep*r
                chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                row = bytearray(rec.n*4); k = 0
                for b in chunk:
                    u = UNPACK[b]
                    row[k] = 1 if u[0] else 0; row[k+1] = 1 if u[1] else 0
                    row[k+2] = 1 if u[2] else 0; row[k+3] = 1 if u[3] else 0
                    k += 4
                old = rows.get(pr)
                if old is None: rows[pr] = row
                else:
                    for i in range(len(row)):
                        if row[i]: old[i] = 1
    return rows

def main():
    rows = decode_rows(FN)
    nz = [y for y in rows if any(rows[y])]
    r0 = min(nz); c0 = 0
    # extract one tile (1024x1024) from content top-left
    T = [bytes(rows[r0 + y][0:P_TILE]) for y in range(P_TILE)] if (r0+P_TILE-1) in rows else None
    if T is None:
        print('tile extraction failed'); return
    ones = sum(sum(row) for row in T)
    print(f'tile 1024x1024: ones={ones} ({ones*100.0/(P_TILE*P_TILE):.2f}%), expected 75% for D>=64 uniform')
    def eq(a, b):
        tot = len(a); e = sum(1 for i in range(tot) if a[i] == b[i])
        return e*100.0/tot
    flat = [v for row in T for v in row]
    print('\n-- symmetry tests (equality %; random≈62.5%) --')
    n = P_TILE
    mirx = [flat[y*n + (n-1-x)] for y in range(n) for x in range(n)]
    miry = [flat[(n-1-y)*n + x] for y in range(n) for x in range(n)]
    rot180 = [flat[(n-1-y)*n + (n-1-x)] for y in range(n) for x in range(n)]
    trans = [flat[x*n + y] for y in range(n) for x in range(n)]
    print(f'  mirror-x: {eq(flat, mirx):.2f}%')
    print(f'  mirror-y: {eq(flat, miry):.2f}%')
    print(f'  rot180  : {eq(flat, rot180):.2f}%')
    print(f'  transpose: {eq(flat, trans):.2f}%')
    # quadrant relations
    h = n//2
    q = []
    for qy in (0, 1):
        for qx in (0, 1):
            q.append([T[qy*h + y][qx*h + x] for y in range(h) for x in range(h)])
    for i in range(4):
        for j in range(4):
            if i < j:
                print(f'  quadrant{i} vs quadrant{j}: {eq(q[i], q[j]):.2f}%')
    # half-tile shift
    for dy, dx in ((0, 512), (512, 0), (512, 512)):
        a = []; b = []
        for y in range(0, n-dy):
            for x in range(0, n-dx):
                a.append(T[y][x]); b.append(T[y+dy][x+dx])
        print(f'  shift ({dy},{dx}): {eq(a, b):.2f}%')
    # check tile row distinctness: number of unique rows vs 1024
    uniq = len(set(bytes(row) for row in T))
    print(f'  unique rows in tile: {uniq}/1024')

if __name__ == '__main__':
    main()
