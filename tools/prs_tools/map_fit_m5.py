#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Brute-force: A3 mode5 plane->ink mapping + 2-bit dot coverage model fit.
Model: tone_ink = x*f1 + y*f2 + z*f3  (f1,f2,f3 = fractions of dot levels 1/2/3
inside image content area), ICC pred = sRGB->v1440x720-A3-DTF-1390.icm B2A intent 0.
"""
import os, itertools, json
from PIL import Image, ImageCms

ROOT = r"D:\work\RIP核心分析"
SRGB = os.path.join(ROOT, r"reference\profiles\source\RGB\SRGB IEC61966-2.1.icc")
DEST = os.path.join(ROOT, r"reference\profiles\source\OUTPUT\v1440x720-A3-DTF-1390.icm")
NAMES = ['flat_c','flat_m','flat_y','flat_k','flat_r','flat_g','flat_b']
RGB = {'flat_c':(0,255,255),'flat_m':(255,0,255),'flat_y':(255,255,0),'flat_k':(0,0,0),
       'flat_r':(255,0,0),'flat_g':(0,255,0),'flat_b':(0,0,255)}
CONTENT = 720000.0  # dots of image content per plane (1200x600)
TOTAL = 3456000.0
# raw hist per plane per color: from prn_color_stats for mode5
HIST = {
 'flat_c': {'00':[3452416,3584,0,0],'01':[3451695,4305,0,0],'02':[3187196,268804,0,0],'04':[3353862,102138,0,0]},
 'flat_m': {'00':[3454488,1512,0,0],'01':[2743137,295292,400600,16971],'02':[3392395,58043,5331,231],'04':[3449576,6424,0,0]},
 'flat_y': {'00':[3455927,73,0,0],'01':[3444672,2162,7413,1753],'02':[3450207,5793,0,0],'04':[2736076,32801,556104,131019]},
 'flat_k': {'00':[2732386,33209,553632,136773],'01':[3169176,281399,5218,207],'02':[3175679,280321,0,0],'04':[2743886,306127,390338,15649]},
 'flat_r': {'00':[3455748,252,0,0],'01':[2726425,6726,510462,212387],'02':[3445460,1031,6702,2807],'04':[2736011,1962,464009,254018]},
 'flat_g': {'00':[3453542,2458,0,0],'01':[3443977,2435,5949,3639],'02':[3270843,185157,0,0],'04':[2736011,1036,446137,272816]},
 'flat_b': {'00':[3437675,11056,6731,538],'01':[2812865,556353,86319,463],'02':[2729445,179820,506411,40324],'04':[3447992,8008,0,0]},
}
PLANES = ['00','01','02','04']

def preds(intent=0):
    inp = ImageCms.getOpenProfile(SRGB)
    outp = ImageCms.getOpenProfile(DEST)
    tr = ImageCms.buildTransform(inp, outp, 'RGB','CMYK', renderingIntent=intent, flags=0)
    out = {}
    for nm in NAMES:
        c = ImageCms.applyTransform(Image.new('RGB',(1,1),RGB[nm]), tr).getpixel((0,0))
        out[nm] = dict(C=c[0]/255.0,M=c[1]/255.0,Y=c[2]/255.0,K=c[3]/255.0)
    return out

def fit_xyz(rows):
    """rows: list of (f1,f2,f3,pred). LSQ solve 3 unknowns."""
    A=[[0.0]*3 for _ in range(3)]; b=[0.0]*3
    for f1,f2,f3,t in rows:
        f=[f1,f2,f3]
        for i in range(3):
            b[i]+=f[i]*t
            for j in range(3):
                A[i][j]+=f[i]*f[j]
    # gaussian elim
    import copy
    M=[A[i][:]+[b[i]] for i in range(3)]
    for i in range(3):
        p=max(range(i,3), key=lambda r: abs(M[r][i]))
        if abs(M[p][i])<1e-12: return None
        M[i],M[p]=M[p],M[i]
        for r in range(3):
            if r!=i:
                f=M[r][i]/M[i][i]
                for c in range(i,4): M[r][c]-=f*M[i][c]
    x=[M[i][3]/M[i][i] for i in range(3)]
    rms=(sum((x[0]*f1+x[1]*f2+x[2]*f3-t)**2 for f1,f2,f3,t in rows)/len(rows))**0.5
    return x, rms

def main():
    P = preds(0)
    results=[]
    for perm in itertools.permutations(['C','M','Y','K']):
        mp = dict(zip(PLANES, perm))
        rows=[]
        for nm in NAMES:
            for pl in PLANES:
                ink = mp[pl]
                hs = HIST[nm][pl]
                f1,f2,f3 = hs[1]/CONTENT, hs[2]/CONTENT, hs[3]/CONTENT
                rows.append((f1,f2,f3,P[nm][ink]))
        r = fit_xyz(rows)
        if r is None: continue
        x,rms = r
        results.append((rms, mp, x))
    results.sort()
    for rms, mp, x in results[:8]:
        print(f'rms={rms:.4f} map={mp} x=({x[0]:.3f},{x[1]:.3f},{x[2]:.3f})')
    # details for best
    rms, mp, x = results[0]
    print('\nBEST details:', mp, x)
    for nm in NAMES:
        parts=[]
        for pl in PLANES:
            ink=mp[pl]; hs=HIST[nm][pl]
            f1,f2,f3 = hs[1]/CONTENT, hs[2]/CONTENT, hs[3]/CONTENT
            model = x[0]*f1+x[1]*f2+x[2]*f3
            parts.append(f'{ink}({pl}):{model:.2f}/{P[nm][ink]:.2f}')
        print(f'  {nm:8s} ' + ' '.join(parts))

if __name__ == '__main__':
    main()
