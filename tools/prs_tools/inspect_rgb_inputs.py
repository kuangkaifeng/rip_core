#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inspect the rgbcube9 / rgb ramps16 input images."""
import os
from PIL import Image
from collections import Counter
ROOT = r"D:\work\RIP核心分析"
INP = os.path.join(ROOT, 'reference', 'inputs')

for fn in ('probe_rgbcube9_540.png', 'probe_screen_rgb_ramps16_160.png'):
    p = os.path.join(INP, fn)
    if not os.path.exists(p):
        print(fn, 'MISSING'); continue
    im = Image.open(p)
    print('=' * 80)
    print(fn, im.mode, im.size, im.info.get('dpi'))
    rgb = im.convert('RGB')
    px = rgb.load(); W, H = rgb.size
    # sample grid
    print('  sample colors:')
    for y in [0, H // 4, H // 2, 3 * H // 4, H - 1]:
        row = []
        for x in range(0, W, max(1, W // 8)):
            row.append(px[x, y])
        print(f'   y={y:4d}: {row}')
    # unique colors along middle row / column
    midy = H // 2
    colors = [px[x, midy] for x in range(W)]
    uniq = []
    for c in colors:
        if not uniq or uniq[-1][0] != c:
            uniq.append([c, 1])
        else:
            uniq[-1][1] += 1
    print(f'  middle row runs: {[(c, n) for c, n in uniq][:20]}')
