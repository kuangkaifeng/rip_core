#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A3 mode5 (colorCorrection=true) validation: measured per-plane linear coverage vs
ICC prediction using dist v1440x720-A3-DTF-1390.icm B2A, plane mapping hypothesis
0x00=K,0x01=M,0x02=C,0x04=Y (+ 0x11/0x12 = W1/W2 empty)."""
import os
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
DEST = os.path.join(ROOT, r"reference\profiles\source\OUTPUT\v1440x720-A3-DTF-1390.icm")
RGB = {'flat_c':(0,255,255),'flat_m':(255,0,255),'flat_y':(255,255,0),'flat_k':(0,0,0),
       'flat_r':(255,0,0),'flat_g':(0,255,0),'flat_b':(0,0,255)}
CONTENT = 0.208
# measured normalized coverage: [K(00), M(01), C(02), Y(04)]
MEAS = {
 'flat_c': [0.0, 0.0, 0.374, 0.142],
 'flat_m': [0.0, 0.534, 0.034, 0.005],
 'flat_y': [0.0, 0.010, 0.008, 0.712],
 'flat_k': [0.721, 0.135, 0.130, 0.524],
 'flat_r': [0.0, 0.774, 0.009, 0.784],
 'flat_g': [0.0, 0.010, 0.087, 0.793],
 'flat_b': [0.0, 0.337, 0.611, 0.005],
}
NAMES = ['flat_c','flat_m','flat_y','flat_k','flat_r','flat_g','flat_b']
PLANES = ['K','M','C','Y']
ORDER = ['C','M','Y','K']  # ICC output order

def main():
    inp = ImageCms.getOpenProfile(SRGB)
    outp = ImageCms.getOpenProfile(DEST)
    print('dest:', ImageCms.getProfileName(outp).strip())
    for intent in (0,1,2):
        tr = ImageCms.buildTransform(inp, outp, 'RGB','CMYK', renderingIntent=intent, flags=0)
        errs = []
        print(f'--- intent {intent} ---')
        for nm in NAMES:
            im = Image.new('RGB',(1,1),RGB[nm])
            c = ImageCms.applyTransform(im, tr).getpixel((0,0))
            pred = dict(C=c[0]/255.0, M=c[1]/255.0, Y=c[2]/255.0, K=c[3]/255.0)
            row = []
            for i, pl in enumerate(PLANES):
                d = MEAS[nm][i] - pred[pl]
                errs.append(d)
                row.append(f'{pl}:{MEAS[nm][i]:.2f}/{pred[pl]:.2f}({d:+.2f})')
            print(f'  {nm:8s} ' + ' '.join(row))
        rms = (sum(e*e for e in errs)/len(errs))**0.5
        print(f'  rms={rms:.3f}')

if __name__ == '__main__':
    main()
