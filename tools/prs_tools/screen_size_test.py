#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test whether the screening field is independent of content size:
compare observed levels in 100px (patch20) / 160px (ramp16) jobs with the 384x384 field
extracted from 64px probes, at CONTENT coordinates.
Content mapping: content dot (cy,cx) = (6*image_pixel + sub).
"""
import os, sys, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
os.environ['PRN_UNPACK'] = 'msb'
import prn_canvas
from PIL import Image

ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
INPUTS = os.path.join(ROOT, 'reference', 'inputs')
SCREEN = os.path.join(ROOT, 'reference', 'screen')
SIZE = 384; VSTEP = 8
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}

def load_thr(ink):
    d = open(os.path.join(SCREEN, f'thr_{ink}.bin'), 'rb').read()
    return [[(d[(y*SIZE+x)*3], d[(y*SIZE+x)*3+1], d[(y*SIZE+x)*3+2]) for x in range(SIZE)] for y in range(SIZE)]

def tiff(fn):
    im = Image.open(fn); px = im.load(); W, H = im.size
    return [[px[x, y] for x in range(W)] for y in range(H)], W, H

def decode(fn, vstep=VSTEP):
    cvs, info = prn_canvas.decode_canvas(fn, vstep=vstep, verbose=False)
    return cvs, info

def pred(T, v):
    t1, t2, t3 = T
    return (1 if t1 and v >= t1 else 0) + (1 if t2 and v >= t2 else 0) + (1 if t3 and v >= t3 else 0)

def test_job(tag, prn, tif, content_top_shift=0):
    cvs, info = decode(prn)
    ink, W, H = tiff(tif)
    print(f'--- {tag}: image {W}x{H} ---')
    for ch, code in COLOR.items():
        cv = cvs.get(code)
        if cv is None: continue
        T = load_thr(ch)
        top = TOP[ch] + content_top_shift
        tot = mism = 0
        for iy in range(H):
            for ix in range(W):
                v = ink[iy][ix][{'C':0,'M':1,'Y':2,'K':3}[ch]]
                if not v: continue
                for dy in range(6):
                    cy = 6*iy + dy
                    if cy >= SIZE: continue
                    for dx in range(6):
                        cx = 6*ix + dx
                        if cx >= SIZE: continue
                        obs = cv[top+cy][cx]
                        p = pred(T[cy][cx], v)
                        tot += 1
                        if p != obs: mism += 1
        if tot:
            print(f'  {ch}: match={(tot-mism)*100.0/tot:.3f}% over {tot} dots (content coord, area {min(SIZE,6*W)}x{min(SIZE,6*H)})')

if __name__ == '__main__':
    test_job('patch20_100', os.path.join(SAMPLES, 'probe_screen_cmyk_patch20_100_a3dtf1390_m2.prn'),
             os.path.join(INPUTS, 'cmyk_patch20_100.tif'))
    test_job('ramp16_160', os.path.join(SAMPLES, 'probe_screen_cmyk_ramp16_160_a3dtf1390_m2.prn'),
             os.path.join(INPUTS, 'cmyk_ramp16_160.tif'))
