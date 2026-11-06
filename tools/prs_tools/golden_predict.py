#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compare golden PRN measured CMYK coverage (block-mask, mapping 00=C,04=K,11=Y,12=M)
with predictions for the golden RGBA image under several candidate RGB->CMYK transforms."""
import os
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
DIST = r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile"
CAND = {
 'FOGRA39': (os.path.join(DIST, r'CMYK\CoatedFOGRA39.icc'), 'B2A'),
 'SWOP': (os.path.join(DIST, r'CMYK\US Web Coated (SWOP) v2.icc'), 'B2A'),
 'JapanColor': (os.path.join(DIST, r'DEFAULT\Default_cmyk.icc'), 'B2A'),
 'A3_dest_v1440x720': (os.path.join(ROOT, r'reference\profiles\source\OUTPUT\v1440x720-A3-DTF-1390.icm'), 'B2A'),
}
# measured block-mask coverage from 1793946733280.prn (mapping 00=C,04=K,11=Y,12=M)
MEAS = dict(C=0.0, K=0.0, Y=0.0, M=0.0)

def image_pixels():
    im = Image.open(PNG).convert('RGBA')
    W,H = im.size
    px = im.load()
    out=[]
    for y in range(H):
        for x in range(W):
            r,g,b,a = px[x,y]
            if a==0: continue
            out.append((r,g,b))
    return out

def predict_transform(path, intent, pixels):
    inp = ImageCms.getOpenProfile(SRGB)
    outp = ImageCms.getOpenProfile(path)
    tr = ImageCms.buildTransform(inp, outp, 'RGB','CMYK', renderingIntent=intent, flags=0)
    n=len(pixels)
    sums=[0.0]*4
    # batch 1x1
    for (r,g,b) in pixels:
        c = ImageCms.applyTransform(Image.new('RGB',(1,1),(r,g,b)), tr).getpixel((0,0))
        for i in range(4): sums[i]+=c[i]
    return [s/(n*255.0) for s in sums]  # C,M,Y,K means over covered pixels

def predict_naive(pixels):
    n=len(pixels); sums=[0,0,0,0]
    for (r,g,b) in pixels:
        k = min(r,g,b)  # simple UCR: K = min
        K = 255-k
        if K==255:
            C=M=Y=0
        else:
            C=(255-r-K)*255//(255-K) if K<255 else 0
            M=(255-g-K)*255//(255-K) if K<255 else 0
            Y=(255-b-K)*255//(255-K) if K<255 else 0
        sums[0]+=C; sums[1]+=M; sums[2]+=Y; sums[3]+=K
    return [s/(n*255.0) for s in sums]

def main():
    pix = image_pixels()
    print(f'golden painted pixels: {len(pix)}')
    print('naive formula (K=min):', [round(v,3) for v in predict_naive(pix)])
    res={}
    for tag,(path,_) in CAND.items():
        for intent in (0,1,2):
            m = predict_transform(path, intent, pix)
            res[f'{tag}/i{intent}'] = m
            print(f'{tag:18s} intent={intent}: C,M,Y,K = ' + ', '.join(f'{v:.3f}' for v in m))

if __name__=='__main__':
    main()
