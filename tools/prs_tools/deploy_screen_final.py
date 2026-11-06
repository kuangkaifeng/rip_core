#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Deploy final screen payload: direct-extraction 1024 tiles (prs-analyst version, best accuracy).

Writes: reference/screen/final (canonical), build/screen, reference/screen, reference/screen/engine,
        reference/screen/legacy384 (384 top-left crop).
"""
import os, json, shutil
ROOT = r"D:\work\RIP核心分析"
REF = os.path.join(ROOT, 'reference', 'screen')
FINAL = os.path.join(REF, 'final')
ENG = os.path.join(REF, 'engine')
BUILD = os.path.join(ROOT, 'build', 'screen')
LEG = os.path.join(REF, 'legacy384')
TILE = 1024

VAL = dict(
    content_384='C=100.0000%, M=99.9763%, Y=99.9769%, K=100.0000%',
    content_1056='C/M/Y/K = 100.0000%',
    residual_note='content=384 M/Y residuals are exactly the oracle never-printed row-383 pixels (weave gap), not screen errors',
)
META = dict(
    version=6, size=TILE, tile_size=TILE,
    engine_rule='level(v,x,y) = (v>=T1)+(v>=T2)+(v>=T3); thr_<ink>.bin = size*size*3 bytes [T1,T2,T3] uint8 raster order y*size+x; 0=never',
    coordinate_indexing=dict(type='content-relative', tile_indexing='D(x,y)=TILE[x%1024][y%1024]'),
    channels=[dict(ink=ink, file=f'thr_{ink}.bin',
                   content_top_page_row=640 if ink in ('C', 'K') else 644,
                   source=f'direct extraction from probe_scan_{ink}###_176 (256 levels)') for ink in 'CMYK'],
    decoder_convention='ESC/P2 2bit MSB-first; prow = pos_k + 8*r - content_top; nonzero merge; identical to tools/validate/validate_e2e.py::decode_page',
    validation=dict(under_lead_decoder=VAL),
    holes=dict(C=0, M=16, Y=0, K=16,
               note='M/K 16 positions are never printed by oracle (obs=0 at all tones) => 0=never is correct; do not fill'),
    compare_vs_lead_tile='lead engine1024: 99.965-99.990%; this direct extraction better on all channels/contents',
)

def main():
    os.makedirs(FINAL, exist_ok=True)
    # source = reference/screen/engine (direct extraction, unfilled)
    for ink in 'CMYK':
        shutil.copyfile(os.path.join(ENG, f'thr_{ink}.bin'), os.path.join(FINAL, f'thr_{ink}.bin'))
        d = open(os.path.join(FINAL, f'thr_{ink}.bin'), 'rb').read()
        D = bytearray()
        for i in range(TILE*TILE):
            t1, t2, t3 = d[i*3], d[i*3+1], d[i*3+2]
            lo, hi = 0, 255
            if t1: lo = max(lo, 256-3*t1); hi = min(hi, 258-3*t1)
            if t2: lo = max(lo, 512-3*t2); hi = min(hi, 514-3*t2)
            if t3: lo = max(lo, 768-3*t3); hi = min(hi, 770-3*t3)
            D.append(max(0, min(255, round((lo+hi)/2))))
        open(os.path.join(FINAL, f'D_{ink}.bin'), 'wb').write(D)
    with open(os.path.join(FINAL, 'screen_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(META, f, indent=1, ensure_ascii=False)
    # deploy
    for dst in (BUILD, REF, ENG):
        os.makedirs(dst, exist_ok=True)
        for ink in 'CMYK':
            shutil.copyfile(os.path.join(FINAL, f'thr_{ink}.bin'), os.path.join(dst, f'thr_{ink}.bin'))
            shutil.copyfile(os.path.join(FINAL, f'D_{ink}.bin'), os.path.join(dst, f'D_{ink}.bin'))
        shutil.copyfile(os.path.join(FINAL, 'screen_meta.json'), os.path.join(dst, 'screen_meta.json'))
    # legacy 384 crop
    os.makedirs(LEG, exist_ok=True)
    for ink in 'CMYK':
        d = open(os.path.join(FINAL, f'thr_{ink}.bin'), 'rb').read()
        buf = bytearray()
        for y in range(384):
            for x in range(384):
                o = (y*TILE + x)*3
                buf.extend(d[o:o+3])
        open(os.path.join(LEG, f'thr_{ink}.bin'), 'wb').write(bytes(buf))
    open(os.path.join(LEG, 'screen_meta.json'), 'w', encoding='utf-8').write(
        json.dumps(dict(size=384, tile_size=TILE, engine_rule=META['engine_rule'],
                        note='legacy 384 top-left crop of the 1024 tile'), indent=1))
    print('deployed: reference/screen/final, build/screen, reference/screen, reference/screen/engine, reference/screen/legacy384')

if __name__ == '__main__':
    main()
