#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fit dot-size coverage model: coverage = a1*frac1 + a2*frac2 + 1*frac3
using H13 HSSF flat-color PRNs (measured per-plane hist) vs ICC-predicted CMYK.
Also test A3 ESC/P2 flat-color PRNs with same model (mode 2, 4 planes)."""
import os, sys, json, importlib.util
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
DEST_H13 = r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\OUTPUT\v720x720-dtf.icm"
SAMPLES = os.path.join(ROOT, r"reference\prn_samples")

# measured H13 m0 plane stats (from hssf_planes.py): plane order assumed K,C,M,Y,W1
H13_MEAS = {   # name: per-plane hist [0,1,2,3] counts for planes K,C,M,Y
 'flat_c':   [[364800,0,0,0],[282826,81974,0,0],[364118,682,0,0],[311950,52850,0,0]],
 'flat_m':   [[364800,0,0,0],[269368,95432,0,0],[41035,276713,46778,274],[362565,2235,0,0]],
 'flat_y':   [[364800,0,0,0],[357925,6875,0,0],[364066,734,0,0],[4811,5829,262024,92136]],
 'flat_k':   [[4804,0,3522,356474],[4851,18529,279228,62192],[5689,80989,256445,21677],[4844,17275,278539,64142]],
 'flat_r':   [[364800,0,0,0],[363700,1100,0,0],[4806,0,41930,318064],[4800,0,77887,282113]],
 'flat_g':   [[364800,0,0,0],[138437,225726,637,0],[363969,831,0,0],[6367,104980,237931,15522]],
 'flat_b':   [[320985,43815,0,0],[4800,0,2090,357910],[5323,63072,268244,28161],[364709,91,0,0]],
}
NAMES = ['flat_c','flat_m','flat_y','flat_k','flat_r','flat_g','flat_b']
RGB = {'flat_c':(0,255,255),'flat_m':(255,0,255),'flat_y':(255,255,0),'flat_k':(0,0,0),
       'flat_r':(255,0,0),'flat_g':(0,255,0),'flat_b':(0,0,255)}

def predict(intent):
    inp = ImageCms.getOpenProfile(SRGB)
    outp = ImageCms.getOpenProfile(DEST_H13)
    tr = ImageCms.buildTransform(inp, outp, 'RGB', 'CMYK', renderingIntent=intent, flags=0)
    out = {}
    for name, rgb in RGB.items():
        im = Image.new('RGB', (1,1), rgb)
        c = ImageCms.applyTransform(im, tr).getpixel((0,0))
        out[name] = [c[3]/255.0, c[0]/255.0, c[1]/255.0, c[2]/255.0]  # reorder to K,C,M,Y
    return out

def fit(meas, pred, names):
    # least squares for a1,a2: pred_c = a1*f1 + a2*f2 + 1*f3
    # build normal equations over all channels
    A = [[0.0,0.0],[0.0,0.0]]; b = [0.0,0.0]
    rows = []
    for name in names:
        hists = meas[name]
        pm = pred[name]
        for ch in range(4):
            hs = hists[ch]
            n = sum(hs) or 1
            f1, f2, f3 = hs[1]/n, hs[2]/n, hs[3]/n
            target = pm[ch] - f3
            rows.append((f1, f2, target, name, ch, pm[ch], f1+f2+f3))
            A[0][0] += f1*f1; A[0][1] += f1*f2
            A[1][0] += f1*f2; A[1][1] += f2*f2
            b[0] += f1*target; b[1] += f2*target
    det = A[0][0]*A[1][1]-A[0][1]*A[1][0]
    a1 = (b[0]*A[1][1]-A[0][1]*b[1])/det
    a2 = (A[0][0]*b[1]-b[0]*A[1][0])/det
    # residuals
    res = []
    for f1,f2,t,name,ch,pc,cov in rows:
        pred_cov = a1*f1 + a2*f2 + (cov - f1 - f2)
        res.append((name, ch, pc, pred_cov, pred_cov-pc))
    return a1, a2, res

def main():
    for intent in (0,1,2):
        pred = predict(intent)
        a1,a2,res = fit(H13_MEAS, pred, NAMES)
        err = [r[4] for r in res]
        rms = (sum(e*e for e in err)/len(err))**0.5
        print(f'intent={intent}: fitted a1={a1:.3f} a2={a2:.3f} rms={rms:.3f} maxerr={max(err, key=abs):+.3f}')
        for r in res:
            print(f'   {r[0]:8s} ch{r[1]} pred={r[2]:.3f} model={r[3]:.3f} diff={r[4]:+.3f}')

if __name__ == '__main__':
    main()

