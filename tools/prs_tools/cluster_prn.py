#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cluster PRN dot patterns into flat-color regions; compare with ICC-predicted ink vectors."""
import os, pickle, json, sys
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
PKL = os.path.join(ROOT, r"work\prs\golden_prn_planes.pkl")
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
DESTDIR = os.path.join(ROOT, r"reference\profiles\source\OUTPUT")

def unpack(row):
    out = bytearray(len(row)*4)
    k = 0
    for b in row:
        out[k] = (b >> 6) & 3
        out[k+1] = (b >> 4) & 3
        out[k+2] = (b >> 2) & 3
        out[k+3] = b & 3
        k += 4
    return out

def load_planes():
    with open(PKL, 'rb') as f:
        obj = pickle.load(f)
    blocks = obj['blocks']
    colors = sorted({c for adv, recs in blocks for c in recs})
    W = None
    for adv, recs in blocks:
        for c, raw in recs.items():
            W = len(unpack(raw)) if raw else None
            break
        if W: break
    # approximate y mapping
    ys = []
    y = 0
    for adv, recs in blocks:
        ys.append(y)
        y += adv if adv else 90
    H = y + 90
    print(f'colors={colors} W={W} approx H={H} blocks={len(blocks)}')
    # decode all
    planes = {c: [[0]*W for _ in range(H)] for c in colors}
    for bi, (adv, recs) in enumerate(blocks):
        y0 = ys[bi]
        for c, raw in recs.items():
            if raw is None: continue
            rb = unpack(raw)
            n = len(rb)//90
            for r in range(90):
                yy = y0 + r
                if yy >= H: break
                planes[c][yy] = list(rb[r*n:(r+1)*n])
    return colors, planes, W, H

def tile_means(colors, planes, W, H, T=64):
    tw, th = W//T, H//T
    # per tile per channel mean
    tiles = {}
    for c in colors:
        arr = []
        pl = planes[c]
        for ty in range(th):
            row = []
            for tx in range(tw):
                s = 0; n = 0
                for y in range(ty*T, (ty+1)*T):
                    py = pl[y]
                    s += sum(py[tx*T:(tx+1)*T]); n += T
                row.append(s/n if n else 0)
            arr.append(row)
        tiles[c] = arr
    # Now cluster tiles by 4-channel vector; use histogram of exact rounded vectors
    from collections import Counter
    vecs = Counter()
    for ty in range(th):
        for tx in range(tw):
            v = tuple(round(tiles[c][ty][tx], 1) for c in colors)
            vecs[v] += 1
    print(f'\nTop tile vectors (T={T}, {tw}x{th} tiles):')
    for v, n in vecs.most_common(15):
        print('  ', v, 'x', n)
    return tiles, vecs

def predict_rgb(rgb):
    out = {}
    for dest in ('v1440x720-A3-DTF-1390.icm',):
        for intent in (0, 1, 2):
            inp = ImageCms.getOpenProfile(SRGB)
            outp = ImageCms.getOpenProfile(os.path.join(DESTDIR, dest))
            tr = ImageCms.buildTransform(inp, outp, 'RGB', 'CMYK', renderingIntent=intent, flags=0)
            im = Image.new('RGB', (1, 1), rgb)
            c = ImageCms.applyTransform(im, tr).getpixel((0, 0))
            out[f'{dest}/intent{intent}'] = [x/255.0 for x in c]
    return out

def main():
    colors, planes, W, H = load_planes()
    tiles, vecs = tile_means(colors, planes, W, H)
    print('\nPredicted CMYK (fraction) for key RGB colors:')
    for name, rgb in [('red', (192, 0, 23)), ('blue', (25, 3, 137)),
                      ('black', (0, 0, 0)), ('white', (255, 255, 255))]:
        print(f'  {name} {rgb}:')
        for k, v in predict_rgb(rgb).items():
            print(f'    {k}: ' + ', '.join(f'{x:.3f}' for x in v))

if __name__ == '__main__':
    main()
