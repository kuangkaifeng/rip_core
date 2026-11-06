#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inspect reference/inputs images: mode, size, dominant colors."""
import os, sys
from PIL import Image
from collections import Counter

D = r"D:\work\RIP核心分析\reference\inputs"
for fn in sorted(os.listdir(D)):
    p = os.path.join(D, fn)
    try:
        im = Image.open(p)
        info = dict(mode=im.mode, size=im.size)
        if 'dpi' in im.info: info['dpi'] = im.info['dpi']
        colors = Counter(im.convert('RGBA').getdata())
        top = colors.most_common(4)
        print(f'{fn:28s} {im.mode:5s} {im.size} {info.get("dpi","")} top={top}')
    except Exception as e:
        print(f'{fn}: ERR {e}')
