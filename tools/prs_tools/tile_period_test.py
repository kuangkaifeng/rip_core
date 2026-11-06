#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tile-period test for the stochastic screen using the 720x720 C64 probe
(content 4320x4320 device dots). At v=64: level = [D>=64] (binary), so periodicity
of D would show up as periodicity of the level pattern.
"""
import os, sys, collections, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
ROOT = r"D:\work\RIP核心分析"
FN = os.path.join(ROOT, 'reference', 'prn_samples', 'probe_scan_C64_720_a3dtf1390_m2.prn')
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

def decode_binary(fn, code=0x00, vstep=8):
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    pos = 0
    rows = {}
    W = 0
    for blk in job.blocks:
        if blk.advance is not None:
            pos += blk.advance
        for rec in blk.records:
            if rec.color != code or not rec.raw:
                continue
            W = max(W, rec.n*4)
            for r in range(rec.m):
                pr = pos + vstep*r
                chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                row = bytearray(rec.n*4)
                k = 0
                for b in chunk:
                    u = UNPACK[b]
                    row[k] = 1 if u[0] else 0; row[k+1] = 1 if u[1] else 0
                    row[k+2] = 1 if u[2] else 0; row[k+3] = 1 if u[3] else 0
                    k += 4
                old = rows.get(pr)
                if old is None:
                    rows[pr] = row
                else:
                    for i in range(len(row)):
                        if row[i]: old[i] = 1
    H = max(rows)+1 if rows else 0
    return rows, W, H, job

def main():
    rows, W, H, job = decode_binary(FN)
    nz = [y for y in rows if any(rows[y])]
    print(f'canvas W={W} H={H} blocks={len(job.blocks)} rows_with_ink={len(nz)} range={min(nz)}..{max(nz)}')
    r0, r1 = min(nz), max(nz)
    Hc = r1-r0+1
    print(f'content rows={r0}..{r1} (h={Hc}), W={W}')
    # sample rows and test period in x for candidate periods
    print('-- horizontal period test (equality rate; random≈0.625 for 75% ones) --')
    sample_rows = [r0, r0+100, r0+500, r0+1000, r0+2000, r0+3000, r1-10]
    for P in (64, 96, 128, 192, 256, 320, 384, 512, 640, 768, 960, 1024, 1280, 1440, 1920, 2160):
        if P >= W: continue
        tot = eq = 0
        for y in sample_rows:
            if y not in rows: continue
            row = rows[y]
            for x in range(0, W-P, 7):
                tot += 1
                if row[x] == row[x+P]: eq += 1
        print(f'  P={P:5d}: eq={eq*100.0/max(1,tot):.3f}%')
    print('-- vertical period test --')
    for P in (64, 96, 128, 192, 256, 320, 384, 512, 640, 768, 960, 1024, 1280, 1440, 1920, 2160):
        if P >= Hc: continue
        tot = eq = 0
        for y in range(r0, r1-P, 7):
            if y not in rows or (y+P) not in rows: continue
            ra, rb = rows[y], rows[y+P]
            for x in range(0, W, 11):
                tot += 1
                if ra[x] == rb[x]: eq += 1
        print(f'  P={P:5d}: eq={eq*100.0/max(1,tot):.3f}%')
    # 2D: check exact copies row/col: find duplicate rows via hash of level pattern (sampled)
    print('\n-- duplicate row detection (sampled 1/8 cols, 16-byte hash) --')
    hs = {}
    dups = 0
    for y in range(r0, r1+1, 1):
        if y not in rows: continue
        row = rows[y]
        key = bytes(row[::8])
        if key in hs:
            dups += 1
            if dups <= 5: print(f'   row {y} == row {hs[key]}')
        else:
            hs[key] = y
    print(f'duplicate sampled rows: {dups}')

if __name__ == '__main__':
    main()
