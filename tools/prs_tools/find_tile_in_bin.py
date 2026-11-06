#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Try to locate the 1024x1024 stochastic screen tile directly inside MainTop binaries
(ScreenProcess.dll / mtrip3.dll / driver .pdv ...) using the exactly-known D values
from the 384x384 extraction.
Also verify channel complement relations.
"""
import os, sys, collections

ROOT = r"D:\work\RIP核心分析"
SCREEN = os.path.join(ROOT, 'reference', 'screen')
SIZE = 384

CAND_FILES = [
    r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ScreenProcess.dll",
    r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\mtrip3.dll",
    r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\mtrip.dll",
    r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\MtColorIO.dll",
    r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\mtripNet.exe",
    r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\driver\escpn9_2.pdv",
    r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\ScreenProcess.dll",
]

def load_D(ink):
    d = open(os.path.join(SCREEN, f'D_{ink}.bin'), 'rb').read()
    return [[d[y*SIZE+x] for x in range(SIZE)] for y in range(SIZE)]

def confident_runs(D):
    """yield (y, x0, bytes) runs of >=48 D values that are 'clean' (we can't know confidence
    from file alone; use a heuristic: runs where consecutive values are not repeated?)"""
    out = []
    for y in range(SIZE):
        row = D[y]
        best = None
        for x0 in range(0, SIZE-48, 16):
            run = bytes(row[x0:x0+48])
            # skip runs with stretches of equal values? keep all; many candidates
            out.append((y, x0, run))
    return out

def main():
    D = {ink: load_D(ink) for ink in 'CMYK'}
    runs = confident_runs(D['C'])
    print(f'candidate D runs: {len(runs)}')
    for path in CAND_FILES:
        if not os.path.exists(path):
            print(f'missing {path}'); continue
        data = open(path, 'rb').read()
        print(f'searching {os.path.basename(path)} ({len(data)/1048576:.1f} MB) ...', flush=True)
        found = 0
        for y, x0, run in runs[:200]:
            for variant, pat in (('D', run), ('255-D', bytes(255-v for v in run)),
                                 ('rev', run[::-1])):
                idx = data.find(pat)
                if idx >= 0:
                    print(f'   HIT y={y} x0={x0} variant={variant} at 0x{idx:X}')
                    found += 1
                    if found > 8: break
            if found > 8: break
        if not found:
            print('   no hit in first 200 runs')
    # complement check
    print('\n-- complement relations --')
    for a, b in (('C', 'M'), ('Y', 'K')):
        DA, DB = D[a], D[b]
        ct = collections.Counter(DA[y][x]+DB[y][x] for y in range(SIZE) for x in range(SIZE))
        print(f'  {a}+{b} top sums:', ct.most_common(6))
    # exceptions positions
    DA, DM = D['C'], D['M']
    bad = [(y, x) for y in range(SIZE) for x in range(SIZE) if DA[y][x]+DM[y][x] != 258]
    print(f'  C+M != 258: {len(bad)} pixels; first 10: {bad[:10]}')
    print(f'  C values at bad:', [(DA[y][x], DM[y][x]) for y, x in bad[:20]])

if __name__ == '__main__':
    main()
