#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Finalize build/screen payload:
 - verify C<->M and Y<->K complement relation within extraction uncertainty
 - extract full-tile (1024x1024) binary mask for C at v=64 from probe_scan_C64_720
 - write screen_meta.json (tile 1024, content-relative indexing, known region, relations)
"""
import os, sys, json, collections, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
ROOT = r"D:\work\RIP核心分析"
REF = os.path.join(ROOT, 'reference', 'screen')
BUILD = os.path.join(ROOT, 'build', 'screen')
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
SIZE = 384; TILE = 1024
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

def load_thr(ink, base=REF):
    d = open(os.path.join(base, f'thr_{ink}.bin'), 'rb').read()
    return [[(d[(y*SIZE+x)*3], d[(y*SIZE+x)*3+1], d[(y*SIZE+x)*3+2]) for x in range(SIZE)] for y in range(SIZE)]

def D_interval(t1, t2, t3):
    lo, hi = 0, 255
    if t1:
        lo = max(lo, 256-3*t1); hi = min(hi, 258-3*t1)
    if t2:
        lo = max(lo, 512-3*t2); hi = min(hi, 514-3*t2)
    if t3:
        lo = max(lo, 768-3*t3); hi = min(hi, 770-3*t3)
    return lo, hi

def decode_mask_c64_720():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
    fn = os.path.join(SAMPLES, 'probe_scan_C64_720_a3dtf1390_m2.prn')
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    pos = 0; rows = {}; W = 0
    for blk in job.blocks:
        if blk.advance is not None: pos += blk.advance
        for rec in blk.records:
            if rec.color != 0x00 or not rec.raw: continue
            W = max(W, rec.n*4)
            for r in range(rec.m):
                pr = pos + 8*r
                chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                row = bytearray(rec.n*4); k = 0
                for b in chunk:
                    u = UNPACK[b]
                    row[k] = 1 if u[0] else 0; row[k+1] = 1 if u[1] else 0
                    row[k+2] = 1 if u[2] else 0; row[k+3] = 1 if u[3] else 0
                    k += 4
                old = rows.get(pr)
                if old is None: rows[pr] = row
                else:
                    for i in range(len(row)):
                        if row[i]: old[i] = 1
    nz = [y for y in rows if any(rows[y])]
    r0 = min(nz)
    mask = bytearray()
    for y in range(TILE):
        mask.extend(rows[r0+y][0:TILE])
    return mask

def main():
    print('=== complement relation consistency (within D uncertainty) ===')
    thr = {ink: load_thr(ink) for ink in 'CMYK'}
    rel_report = {}
    for a, b in (('C', 'M'), ('Y', 'K')):
        ok = 0; tot = 0
        for y in range(SIZE):
            for x in range(SIZE):
                Ta = thr[a][y][x]; Tb = thr[b][y][x]
                la, ha = D_interval(*Ta)
                lb, hb = D_interval(*Tb)
                # relation D_b = 258 - D_a  =>  lb..hb overlaps 258-ha..258-la
                lo2, hi2 = 258-ha, 258-la
                if max(lb, lo2) <= min(hb, hi2):
                    ok += 1
                tot += 1
        rel_report[f'{a}<->{b}'] = ok*100.0/tot
        print(f'  {a}<->{b}: D_b=258-D_a consistent for {ok*100.0/tot:.2f}% pixels')

    print('\n=== full-tile binary mask for C at v=64 (from 720x720 probe) ===')
    mask = decode_mask_c64_720()
    ones = sum(mask)
    print(f'  mask: {len(mask)} bytes, ones={ones} ({ones*100.0/len(mask):.2f}%)')
    for base in (REF, BUILD):
        with open(os.path.join(base, 'tile_C64_mask_1024.bin'), 'wb') as f:
            f.write(mask)

    # final meta
    meta = dict(
        version=2,
        size=SIZE,
        tile_size=TILE,
        engine_rule='level(v,x,y) = (v>=T1)+(v>=T2)+(v>=T3); thr_<ink>.bin = known_region_w*known_region_h*3 bytes [T1,T2,T3] uint8 raster order; 0 = never',
        coordinate_indexing=dict(type='content-relative', evidence='base vs margin [5,10,15,20]mm job: 100.000% level match at same content coords (all 4 channels)',
                                 page_origin=dict(note='content top page row per ink; M/Y raster content appears 4 page rows lower than C/K', C=640, M=644, Y=644, K=640)),
        tile=dict(size=TILE, evidence='probe_scan_C64_720 (4320x4320 content): level equality at lag 1024 = 100.000% in x and y; no period 64..960 (~62.5%=random)',
                  indexing='D(x,y) = TILE[x % 1024][y % 1024] on CONTENT coords'),
        known_region=dict(w=SIZE, h=SIZE, note='exact thresholds known only for content x<384,y<384; from 64x64 probe scans (content 384x384)'),
        channels=[
            dict(ink='C', file='thr_C.bin', phaseX=0, phaseY=0, content_top_page_row=640, approx=False),
            dict(ink='M', file='thr_M.bin', phaseX=0, phaseY=0, content_top_page_row=644, approx=False,
                 note='D_M = 258 - D_C (99.6% exact), so M tile derivable from C tile once full C tile known'),
            dict(ink='Y', file='thr_Y.bin', phaseX=0, phaseY=0, content_top_page_row=644, approx=False),
            dict(ink='K', file='thr_K.bin', phaseX=0, phaseY=0, content_top_page_row=640, approx=False,
                 note='D_K = 258 - D_Y (99.6% exact)'),
        ],
        complement_relations=rel_report,
        extra_files=dict(tile_C64_mask_1024=dict(file='tile_C64_mask_1024.bin',
                                                 format='1024*1024 uint8, 1 = (C at v=64 has level>=1, i.e. D>=64)')),
        validation=dict(method='predict level from thr vs decoded probe PRN at content coords',
                        results='C/M/Y/K x tones {16,64,128,192,240,255}: 100.000% pixel match each (content 384x384)'),
        source='probe_scan_<INK>###_a3dtf1390_m2.prn (256 levels), A3-DTF-1390.prs modeId=2, 720x720dpi, 64x64 CMYK probes @120dpi',
        pending='full 1024x1024 tile exact thresholds need 256-level scans on an image with content >=1024x1024 dots (e.g. 176x176 @120dpi) for C and Y (512 jobs); M/K derive by complement.',
    )
    for base in (REF, BUILD):
        with open(os.path.join(base, 'screen_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
    print('\nsaved screen_meta.json (v2) to build/screen and reference/screen')

if __name__ == '__main__':
    main()
