#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Predict CMYK for A3 'no colorCorrection' modes: sRGB -> srcCmyk profile (FOGRA39 / SWOP / Default_cmyk),
compare with measured A3 mode2 flat PRN painted coverages (linear dot model, corrected for painted area)."""
import os
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
PROFILES = {
 'FOGRA39': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\CMYK\CoatedFOGRA39.icc",
 'SWOP': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\CMYK\US Web Coated (SWOP) v2.icc",
 'Default_cmyk': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\DEFAULT\Default_cmyk.icc",
}
RGB = {'flat_c':(0,255,255),'flat_m':(255,0,255),'flat_y':(255,255,0),'flat_k':(0,0,0),
       'flat_r':(255,0,0),'flat_g':(0,255,0),'flat_b':(0,0,255)}
# measured A3 mode2 painted coverage per plane (linear model / painted fraction 0.4112)
# raw linear values from prn_color_stats; painted = linear/0.4112
MEAS = {  # plane order 0x00,0x04,0x11,0x12
 'flat_c': [0.334,0.0,0.094,0.0],
 'flat_m': [0.058,0.0,0.0,0.324],
 'flat_y': [0.036,0.0,0.403,0.0],
 'flat_k': [0.304,0.369,0.274,0.281],
 'flat_r': [0.0,0.0,None,None],
 'flat_g': [None,None,None,None],
 'flat_b': [None,None,None,None],
}
PAINT = 0.4112

def main():
    for tag, prof in PROFILES.items():
        outp = ImageCms.getOpenProfile(prof)
        print(f'=== {tag}: {ImageCms.getProfileName(outp).strip()}')
        for intent in (0,1,2):
            inp = ImageCms.getOpenProfile(SRGB)
            tr = ImageCms.buildTransform(inp, outp, 'RGB', 'CMYK', renderingIntent=intent, flags=0)
            vals = {}
            for name, rgb in RGB.items():
                im = Image.new('RGB',(1,1),rgb)
                c = ImageCms.applyTransform(im, tr).getpixel((0,0))
                vals[name] = [v/255.0 for v in c]
            print(f'  intent {intent}:')
            for name in RGB:
                print(f'    {name:8s} CMYK ' + ', '.join(f'{v:.3f}' for v in vals[name]))

if __name__ == '__main__':
    main()
