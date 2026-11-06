#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fast region analysis of decoded PRN planes: per-tile means via sampling, cluster flat-color regions,
compare with ICC-predicted ink vectors."""
import os, pickle, json, sys
from collections import Counter
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
PKL = os.path.join(ROOT, r"work\prs\golden_prn_planes.pkl")
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
DESTDIR = os.path.join(ROOT, r"reference\profiles\source\OUTPUT")

# byte -> (v0,v1,v2,v3) lookup tables
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

def block_rows(raw, n=1080):
    """yield decoded dot arrays per row from one raw record"""
    for r in range(90):
        chunk = raw[r*n:(r+1)*n]
        row = [0]*(n*4)
        k = 0
        for b in chunk:
            row[k], row[k+1], row[k+2], row[k+3] = UNPACK[b]
            k += 4
        yield row

def load_blocks():
    with open(PKL, 'rb') as f:
        obj = pickle.load(f)
    return obj['blocks']

def main():
    blocks = load_blocks()
    colors = sorted({c for adv, recs in blocks for c in recs})
    n = 1080
    W = n*4
    # cumulative y
    ys = []
    y = 0
    for adv, recs in blocks:
        ys.append(y)
        y += (adv if adv else 90)
    H = y + 90
    print(f'colors={colors} W={W} H~{H} blocks={len(blocks)}')
    # tile means: T=128 dots; sample every 4th row & 4th byte for speed
    T = 128
    tw, th = W//T, H//T
    tile = {c: [[0.0]*tw for _ in range(th)] for c in colors}
    tile_n = {c: [[0]*tw for _ in range(th)] for c in colors}
    for bi, (adv, recs) in enumerate(blocks):
        y0 = ys[bi]
        rows = {c: list(block_rows(recs[c], n)) for c in colors if recs.get(c) and recs[c]}
        for r in range(0, 90, 2):
            yy = y0 + r
            ty = yy // T
            if ty >= th: continue
            for c in rows:
                row = rows[c][r]
                # sample every 4 dots, accumulate into tiles
                for x in range(0, tw*T, 4):
                    tx = x // T
                    tile[c][ty][tx] += row[x]
                    tile_n[c][ty][tx] += 1
        if bi % 10 == 0: print('block', bi, flush=True)
    for c in colors:
        for ty in range(th):
            for tx in range(tw):
                k = tile_n[c][ty][tx]
                if k: tile[c][ty][tx] /= k
    # cluster tiles with sufficient ink
    vecs = Counter()
    for ty in range(th):
        for tx in range(tw):
            v = tuple(round(tile[c][ty][tx], 1) for c in colors)
            if sum(v) > 0.2:
                vecs[v] += 1
    print(f'\nTop ink-tile vectors over all colors {colors} (T={T}, {tw}x{th}):')
    for v, k in vecs.most_common(20):
        print('  ', v, 'x', k)
    json.dump({str(k): n for k, n in vecs.items()},
              open(os.path.join(ROOT, r'work\prs\prn_tile_vectors.json'), 'w'), indent=0)
    print('saved work/prs/prn_tile_vectors.json')

if __name__ == '__main__':
    main()

