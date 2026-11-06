#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compare measured H13 plane coverage (linear dot model) vs ICC predictions using
BOTH candidate v720x720-dtf.icm copies (bin/bin 1904340B vs dist 3633852B)."""
import os
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
CAND = {
 'binbin': r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\ICC Profile\OUTPUT\v720x720-dtf.icm",
 'dist':   r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\OUTPUT\v720x720-dtf.icm",
}
NAMES = ['flat_c','flat_m','flat_y','flat_k','flat_r','flat_g','flat_b']
RGB = {'flat_c':(0,255,255),'flat_m':(255,0,255),'flat_y':(255,255,0),'flat_k':(0,0,0),
       'flat_r':(255,0,0),'flat_g':(0,255,0),'flat_b':(0,0,255)}
# measured plane coverage with linear model (K,C,M,Y planes)
MEAS = {
 'flat_c':   [0.0, 0.0749, 0.0006, 0.0483],
 'flat_m':   [0.0, 0.0872, 0.3388, 0.0020],
 'flat_y':   [0.0, 0.0063, 0.0007, 0.7372],
 'flat_k':   [0.9866, 0.6977, 0.6019, 0.7009],
 'flat_r':   [0.0, 0.0010, 0.9493, 0.9164],
 'flat_g':   [0.0, 0.2071, 0.0008, 0.5735],
 'flat_b':   [0.0400, 0.9845, 0.6252, 0.0001],
}
ORDER = ['K','C','M','Y']

def predict(profile_path, intent):
    inp = ImageCms.getOpenProfile(SRGB)
    outp = ImageCms.getOpenProfile(profile_path)
    tr = ImageCms.buildTransform(inp, outp, 'RGB', 'CMYK', renderingIntent=intent, flags=0)
    out = {}
    for name, rgb in RGB.items():
        im = Image.new('RGB', (1,1), rgb)
        c = ImageCms.applyTransform(im, tr).getpixel((0,0))
        out[name] = [c[3]/255.0, c[0]/255.0, c[1]/255.0, c[2]/255.0]  # K,C,M,Y
    return out

def main():
    for tag, path in CAND.items():
        try:
            name = ImageCms.getProfileName(ImageCms.getOpenProfile(path)).strip()
        except Exception as e:
            print(tag, 'ERR', e); continue
        print(f'=== {tag}: {name}')
        for intent in (0,1,2):
            pred = predict(path, intent)
            errs = []
            lines = []
            for nm in NAMES:
                for ch in range(4):
                    e = MEAS[nm][ch] - pred[nm][ch]
                    errs.append(e)
                    lines.append(f'  {nm:8s} {ORDER[ch]} meas={MEAS[nm][ch]:.3f} pred={pred[nm][ch]:.3f} d={e:+.3f}')
            rms = (sum(e*e for e in errs)/len(errs))**0.5
            mx = max(errs, key=abs)
            print(f'  intent={intent} rms={rms:.4f} max|d|={abs(mx):.3f}')
            if intent == 0 and tag == 'binbin':
                print('\n'.join(lines))

if __name__ == '__main__':
    main()
