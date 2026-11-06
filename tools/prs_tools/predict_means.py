#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Predict page-average CMYK ink fractions for the golden PNG under candidate
ICC chains / intents, and compare with decoded PRN channel means."""
import os, json
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
DESTDIR = os.path.join(ROOT, r"reference\profiles\source\OUTPUT")
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"
STATS = os.path.join(ROOT, r"work\prs\golden_prn_stats.json")

DESTS = ['v1440x720-A3-DTF-1390.icm', 'v1440x1400-A3-DTF-1390.icm', 'v2880x1400-A3-DTF-1390.icm']
INTENTS = [0, 1, 2]   # perceptual, relative colorimetric, saturation
FLAGSETS = [('noBPC', 0), ('BPC', 0x2000)]

def open_profiles(dest):
    inp = ImageCms.getOpenProfile(SRGB)
    outp = ImageCms.getOpenProfile(os.path.join(DESTDIR, dest))
    return inp, outp

def transform_means(dest, intent, flags, composite_white=False, sample_step=1):
    inp, outp = open_profiles(dest)
    tr = ImageCms.buildTransform(inp, outp, 'RGB', 'CMYK', renderingIntent=intent, flags=flags)
    im = Image.open(PNG).convert('RGBA')
    W, H = im.size
    rgb = im.convert('RGB')
    if composite_white:
        bg = Image.new('RGB', (W, H), (255, 255, 255))
        bg.paste(im, (0, 0), im.split()[3])
        rgb = bg
    cmyk = ImageCms.applyTransform(rgb, tr)
    data = list(cmyk.getdata())
    n = len(data)
    sums = [0, 0, 0, 0]
    if not composite_white:
        alpha = list(im.split()[3].getdata())
    else:
        alpha = None
    cnt = 0
    for i in range(0, n, sample_step):
        if alpha is not None and alpha[i] == 0:
            continue
        px = data[i]
        for c in range(4):
            sums[c] += px[c]
        cnt += 1
    # page mean: ink only on painted pixels, page = full raster area
    return dict(dest=dest, intent=intent, flags=flags, composite_white=composite_white,
                sum=sums, cnt=cnt,
                page_mean=[s / (n * 255.0) for s in sums],
                painted_mean=[s / (cnt * 255.0) for s in sums] if cnt else [0]*4)

def main():
    stats = json.load(open(STATS, encoding='utf-8'))
    print('PRN channel stats:')
    for k, v in stats['stats'].items():
        print(f"  color {k}: mean={v['mean']:.4f} mean/3={v['meanfrac']:.4f}")
    print()
    results = []
    for dest in DESTS:
        for intent in INTENTS:
            for fname, flags in FLAGSETS:
                for cw in (False, True):
                    r = transform_means(dest, intent, flags, composite_white=cw, sample_step=2)
                    r['flag_name'] = fname
                    results.append(r)
                    pm = r['page_mean']
                    print(f"{dest:34s} intent={intent} {fname:5s} white={cw!s:5s} page_mean(C,M,Y,K)= "
                          + ', '.join(f'{x:.4f}' for x in pm))
    os.makedirs(os.path.join(ROOT, 'work', 'prs'), exist_ok=True)
    json.dump(results, open(os.path.join(ROOT, r'work\prs\predicted_means.json'), 'w', encoding='utf-8'), indent=1)
    print('saved -> work/prs/predicted_means.json')

if __name__ == '__main__':
    main()
