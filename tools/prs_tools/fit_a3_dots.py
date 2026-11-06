#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fit per-plane 2-bit dot area model for A3 mode2 (no colorCorrection):
coverage_plane = a1*frac1 + a2*frac2 + 1*frac3
against ICC-predicted CMYK using FOGRA39/SWOP/Default intents 0-2.
Plane mapping hypothesis: 0x00=C, 0x04=K, 0x11=Y, 0x12=M (from flat-color evidence)."""
import os, json
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
PROFS = {
 'FOGRA39': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\CMYK\CoatedFOGRA39.icc",
 'SWOP':    r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\CMYK\US Web Coated (SWOP) v2.icc",
 'JapanColor': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\DEFAULT\Default_cmyk.icc",
}
RGB = {'flat_c':(0,255,255),'flat_m':(255,0,255),'flat_y':(255,255,0),'flat_k':(0,0,0),
       'flat_r':(255,0,0),'flat_g':(0,255,0),'flat_b':(0,0,255)}
# measured fractions (zeros outside content excluded): fracs over nonzero dots
# plane order printed: 0x00,0x04,0x11,0x12
MEAS = {
 'flat_c': [[0,0,0.2302,0.181],[0,0,0,0],[0,0,0,0],[0,0,0,0]],
 'flat_m': [[0.1746,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0.2628,0.1483]],
 'flat_y': [[0.1082,0,0,0],[0,0,0,0],[0,0,0.0257,0.3855],[0,0,0,0]],
 'flat_k': [[0,0,0.32,0.0912],[0,0,0.1255,0.2857],[0.0012,0,0.4099,0],[0,0,0.3912,0.0199]],
 'flat_r': [[0,0,0,0],[0,0,0,0],[0,0,0.1483,0.2629],[0,0,0.0694,0.3418]],
 'flat_g': [[0,0,0.0607,0.3505],[0,0,0,0],[0,0,0,0.4112],[0,0,0,0]],
 'flat_b': [[0,0,0.1234,0.2878],[0,0,0,0],[0,0,0,0],[0,0,0.2514,0.1598]],
}
# note: measured fracs listed raw over full raster; content fraction = 0.4112
CONTENT = 0.4112

def meas_cov():
    out = {}
    for nm, planes in MEAS.items():
        # planes: [0x00,0x04,0x11,0x12]; each [f0,f1,f2,f3] raw fractions
        cov = []
        for pl in planes:
            n = sum(pl)
            cov.append(n)  # nonzero fraction of raster
        out[nm] = cov
    return out

def main():
    m = meas_cov()
    # build per-plane nonzero fraction and level fractions
    data = {}
    for nm, planes in MEAS.items():
        data[nm] = []
        for pl in planes:
            nz = sum(pl)
            if nz > 0:
                f1, f2, f3 = pl[1]/nz, pl[2]/nz, pl[3]/nz
            else:
                f1, f2, f3 = 0,0,0
            data[nm].append(dict(nz=nz, f1=f1, f2=f2, f3=f3))
    mapping = {'C':0, 'K':1, 'Y':2, 'M':3}  # plane index in 0x00,0x04,0x11,0x12 order
    for tag, path in PROFS.items():
        outp = ImageCms.getOpenProfile(path)
        for intent in (0,1,2):
            inp = ImageCms.getOpenProfile(SRGB)
            tr = ImageCms.buildTransform(inp, outp, 'RGB','CMYK', renderingIntent=intent, flags=0)
            pred = {}
            for nm, rgb in RGB.items():
                im = Image.new('RGB',(1,1),rgb)
                c = ImageCms.applyTransform(im, tr).getpixel((0,0))
                pred[nm] = dict(C=c[0]/255.0, M=c[1]/255.0, Y=c[2]/255.0, K=c[3]/255.0)
            # fit a1,a2 per plane
            res = []
            for ch, pidx in mapping.items():
                A=[[0.0,0.0],[0.0,0.0]]; b=[0.0,0.0]
                for nm in RGB:
                    d = data[nm][pidx]
                    if d['nz'] <= 0.001: continue
                    # measured coverage of channel ch over content = (nz/CONTENT) * (f1*a1+f2*a2+f3*1)
                    # unknowns scaled by nz/CONTENT; equation: pred_ch = (nz/CONTENT)*(f1*a1+f2*a2+f3)
                    k = d['nz']/CONTENT
                    t = pred[nm][ch] - k*d['f3']
                    x1, x2 = k*d['f1'], k*d['f2']
                    A[0][0]+=x1*x1; A[0][1]+=x1*x2; A[1][0]+=x1*x2; A[1][1]+=x2*x2
                    b[0]+=x1*t; b[1]+=x2*t
                det=A[0][0]*A[1][1]-A[0][1]*A[1][0]
                print("DBG", tag, intent, ch, "A=", A, "b=", b, "det=", det); 
                if abs(det)<1e-12: continue
                a1=(b[0]*A[1][1]-A[0][1]*b[1])/det
                a2=(A[0][0]*b[1]-b[0]*A[1][0])/det
                # residuals
                errs=[]
                for nm in RGB:
                    d=data[nm][pidx]
                    if d['nz']<=0.001: continue
                    k=d['nz']/CONTENT
                    model=k*(a1*d['f1']+a2*d['f2']+d['f3'])
                    errs.append(model-pred[nm][ch])
                rms=(sum(e*e for e in errs)/len(errs))**0.5 if errs else 0
                res.append((ch,a1,a2,rms))
            tot=sum(r[3] for r in res)/len(res)
            print(f'{tag:10s} intent={intent}: ' + '  '.join(f'{ch}:a1={a1:.2f},a2={a2:.2f},rms={rms:.3f}' for ch,a1,a2,rms in res) + f'  avg_rms={tot:.3f}')

if __name__ == '__main__':
    main()

