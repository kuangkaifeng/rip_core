#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze golden PNG content: alpha bbox, color stats, dpi."""
from PIL import Image
import collections

PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"

im = Image.open(PNG)
print('info:', im.info.get('dpi'))
rgba = im.convert('RGBA')
W, H = rgba.size
px = rgba.load()

# alpha bbox + color histogram (on nontransparent)
amin = 255
bbox = [W, H, 0, 0]
colors = collections.Counter()
nontrans = 0
alpha_hist = collections.Counter()
for y in range(H):
    for x in range(W):
        r, g, b, a = px[x, y]
        alpha_hist[a] += 1
        if a > 0:
            nontrans += 1
            if x < bbox[0]: bbox[0] = x
            if y < bbox[1]: bbox[1] = y
            if x > bbox[2]: bbox[2] = x
            if y > bbox[3]: bbox[3] = y
            colors[(r, g, b, a)] += 1
print(f'size={W}x{H} nontransparent={nontrans} ({nontrans*100.0/(W*H):.1f}%)')
print('bbox:', bbox)
print('alpha values top:', alpha_hist.most_common(10))
print('unique nontransparent colors:', len(colors))
print('top 20 colors:', colors.most_common(20))
