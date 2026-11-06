#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cross-check the derived M/K tile against direct 64x64 M/K scans (384x384 region).
Optimize complement offset and report threshold-level agreement for each channel.
"""
import os, sys, math, collections, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
SCREEN = os.path.join(ROOT, 'reference', 'screen')
TILE = 1024
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def direct_thresholds(ink):
    """Extract exact T1/T2/T3 for content 384x384 from 64x64 probe scans."""
    P = load_parser()
    code = COLOR[ink]; top = TOP[ink]; S = 384
    T1 = [[0]*S for _ in range(S)]; T2 = [[0]*S for _ in range(S)]; T3 = [[0]*S for _ in range(S)]
    for t in range(1, 256):
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}_a3dtf1390_m2.prn')
        if not os.path.exists(fn): continue
        d = open(fn, 'rb').read()
        job = P.parse_job(d, decode=True)
        pos = 0
        for blk in job.blocks:
            if blk.advance is not None: pos += blk.advance
            for rec in blk.records:
                if rec.color != code or not rec.raw: continue
                for r in range(rec.m):
                    y = pos + 8*r - top
                    if not (0 <= y < S): continue
                    chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                    for bi, b in enumerate(chunk[:96]):
                        u = UNPACK[b]
                        for k, v in enumerate(u):
                            x = bi*4+k
                            if not v: continue
                            if not T1[y][x]: T1[y][x] = t
                            if v >= 2 and not T2[y][x]: T2[y][x] = t
                            if v >= 3 and not T3[y][x]: T3[y][x] = t
    return T1, T2, T3

def load_tile(ink):
    d = open(os.path.join(SCREEN, f'thr_{ink}.bin'), 'rb').read()
    assert len(d) == TILE*TILE*3
    return d

def tile_triple(d, x, y):
    o = (y*TILE + x)*3
    return (d[o], d[o+1], d[o+2])

def derived_triples(Dc, offset):
    """M thresholds from C D field: D_M = offset - D_C."""
    out = {}
    for y in range(384):
        for x in range(384):
            d = max(0, min(255, offset - Dc[y][x]))
            t1 = math.ceil((256-d)/3); t2 = math.ceil((512-d)/3); t3 = math.ceil((768-d)/3)
            t1 = max(1, min(255, t1)); t2 = max(1, min(255, t2))
            t3 = 0 if t3 > 255 else max(1, t3)
            out[(x, y)] = (t1, t2, t3)
    return out

def D_from_triple(t):
    t1, t2, t3 = t
    lo, hi = 0, 255
    if t1: lo = max(lo, 256-3*t1); hi = min(hi, 258-3*t1)
    if t2: lo = max(lo, 512-3*t2); hi = min(hi, 514-3*t2)
    if t3: lo = max(lo, 768-3*t3); hi = min(hi, 770-3*t3)
    return lo, hi

def main():
    dC = load_tile('C'); dY = load_tile('Y')
    for srcink, dstink in (('C', 'M'), ('Y', 'K')):
        dsrc = dC if srcink == 'C' else dY
        T1, T2, T3 = direct_thresholds(dstink)
        print(f'\n=== {dstink} derived from {srcink}: offset optimization (384x384 direct region) ===')
        best = None
        for offset in range(250, 265):
            ok = tot = 0
            for y in range(384):
                for x in range(384):
                    o = (y*TILE + x)*3
                    lo, hi = D_from_triple((dsrc[o], dsrc[o+1], dsrc[o+2])); srcD = (lo+hi)/2.0
                    d = max(0, min(255, round(offset - srcD)))
                    t1 = math.ceil((256-d)/3); t2 = math.ceil((512-d)/3); t3 = math.ceil((768-d)/3)
                    t1 = max(1, min(255, t1)); t2 = max(1, min(255, t2))
                    t3 = 0 if t3 > 255 else max(1, t3)
                    dr = (t1, t2, t3)
                    di = (T1[y][x], T2[y][x], T3[y][x])
                    if di[0] == 0: continue
                    tot += 1
                    if dr == di: ok += 1
            acc = ok*100.0/max(1, tot)
            print(f'  offset={offset}: threshold-triple match={acc:.3f}%')
            if best is None or acc > best[0]: best = (acc, offset)
        print(f'  BEST offset={best[1]} acc={best[0]:.3f}%')
        # per-threshold agreement at best offset
        ok = collections.Counter()
        for y in range(384):
            for x in range(384):
                o = (y*TILE + x)*3
                lo, hi = D_from_triple((dsrc[o], dsrc[o+1], dsrc[o+2])); srcD = (lo+hi)/2.0
                d = max(0, min(255, round(best[1] - srcD)))
                t1 = max(1, min(255, math.ceil((256-d)/3)))
                t2 = max(1, min(255, math.ceil((512-d)/3)))
                t3 = math.ceil((768-d)/3); t3 = 0 if t3 > 255 else max(1, t3)
                di = (T1[y][x], T2[y][x], T3[y][x])
                if di[0] == 0: continue
                for k, (a, b) in enumerate(zip((t1, t2, t3), di)):
                    ok[k] += (a == b)
        tot = sum(1 for y in range(384) for x in range(384) if T1[y][x] != 0)
        print(f'  per-threshold match: T1={ok[0]*100.0/tot:.3f}% T2={ok[1]*100.0/tot:.3f}% T3={ok[2]*100.0/tot:.3f}%')

if __name__ == '__main__':
    main()
