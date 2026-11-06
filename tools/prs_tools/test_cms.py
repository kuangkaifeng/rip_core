#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test Pillow ImageCms transforms with MainTop profiles; dump stats of golden PNG."""
import sys
from PIL import Image, ImageCms

SRGB = r"D:\work\RIP核心分析\reference\profiles\source\RGB\SRGB IEC61966-2.1.icc"
FOGRA = r"D:\work\RIP核心分析\reference\profiles\source\CMYK\CoatedFOGRA39.icc"
DEST = r"D:\work\RIP核心分析\reference\profiles\source\OUTPUT\v1440x720-A3-DTF-1390.icm"
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"

def info(fn):
    p = ImageCms.getOpenProfile(fn)
    print(f'--- {fn}')
    print('  name:', ImageCms.getProfileName(p).strip())
    print('  desc:', ImageCms.getProfileDescription(p).strip()[:200])
    print('  info:', ImageCms.getProfileInfo(p).strip()[:300].replace('\n',' | '))
    return p

def main():
    for fn in (SRGB, FOGRA, DEST):
        try:
            info(fn)
        except Exception as e:
            print('ERR', fn, e)
    im = Image.open(PNG)
    print('PNG:', im.mode, im.size, im.info.keys())
    if 'icc_profile' in im.info:
        print('  embedded ICC profile bytes:', len(im.info['icc_profile']))
        print('  head:', im.info['icc_profile'][:4], im.info['icc_profile'][36:40])
    rgba = im.convert('RGBA')
    # some sample pixels
    for xy in [(0,0),(359,327),(100,100),(400,300),(200,500)]:
        print('  px', xy, rgba.getpixel(xy))
    # RGB stats
    rgb = rgba.convert('RGB')
    hist = rgb.histogram()
    import collections
    # count alpha distribution
    a = rgba.getchannel('A')
    print('  alpha min/max:', a.getextrema())

if __name__ == '__main__':
    main()
