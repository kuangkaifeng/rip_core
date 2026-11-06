#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Predict device CMYK for flat RGB colors using sRGB -> OUTPUT profile B2A, all intents.
Compare with H13 PRN measured plane coverage."""
import os, sys
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
# H13 dest profile not yet copied; use dist
DEST_H13 = r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\OUTPUT\v720x720-dtf.icm"

COLORS = {
    'flat_c': (0, 255, 255),
    'flat_m': (255, 0, 255),
    'flat_y': (255, 255, 0),
    'flat_k': (0, 0, 0),
    'flat_r': (255, 0, 0),
    'flat_g': (0, 255, 0),
    'flat_b': (0, 0, 255),
    'flat_white': (255, 255, 255),
}

def main():
    inp = ImageCms.getOpenProfile(SRGB)
    outp = ImageCms.getOpenProfile(DEST_H13)
    print('dest profile:', ImageCms.getProfileName(outp).strip())
    for intent in (0, 1, 2):
        tr = ImageCms.buildTransform(inp, outp, 'RGB', 'CMYK', renderingIntent=intent, flags=0)
        print(f'--- intent {intent} ---')
        for name, rgb in COLORS.items():
            im = Image.new('RGB', (1, 1), rgb)
            c = ImageCms.applyTransform(im, tr).getpixel((0, 0))
            print(f'  {name:10s} {str(rgb):16s} -> CMYK {c}  frac=' + ', '.join(f'{v/255:.3f}' for v in c))

if __name__ == '__main__':
    main()
