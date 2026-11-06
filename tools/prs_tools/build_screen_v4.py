#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Assemble the FINAL engine screen payload v4 from exact per-ink 1024 tiles
(reference/screen/tile_<ink>_1024.bin, extracted by extract_176_ink.py from 176x176
256-level probe scans).

Writes:
  build/screen/                size=1024 (for engine)
  reference/screen/            size=1024
  reference/screen/engine/     size=1024 (deployment copy)
  reference/screen/legacy384/  size=384 (top-left crop; for old engine builds)
Validates under lead's decoder (tools/validate/validate_e2e.py::decode_page):
  64px probes  (content=384) and 176px probes (content=1056) for all 4 inks.
"""
import os, sys, json, importlib.util
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
REF = os.path.join(ROOT, 'reference', 'screen')
BUILD = os.path.join(ROOT, 'build', 'screen')
ENG = os.path.join(REF, 'engine')
LEG = os.path.join(REF, 'legacy384')
TILE = 1024
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}
TONES = (0, 16, 64, 128, 192, 240, 255)

def load_decoder():
    spec = importlib.util.spec_from_file_location("validate_e2e", os.path.join(ROOT, 'tools', 'validate', 'validate_e2e.py'))
    V = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(V)
    except SystemExit:
        pass
    return V

def main():
    V = load_decoder()
    tiles = {}
    for ink in ('C', 'M', 'Y', 'K'):
        fn = os.path.join(REF, f'tile_{ink}_1024.bin')
        if not os.path.exists(fn):
            print(f'MISSING {fn}; run extract_176_ink.py {ink} first'); return
        d = open(fn, 'rb').read()
        assert len(d) == TILE*TILE*3, (ink, len(d))
        miss = sum(1 for i in range(TILE*TILE) if d[i*3] == 0)
        print(f'{ink}: tile loaded, T1=0 pixels={miss}')
        tiles[ink] = d
    def write_set(base, size):
        os.makedirs(base, exist_ok=True)
        chans = []
        for ink in ('C', 'M', 'Y', 'K'):
            d = tiles[ink]
            if size == TILE:
                out = d
            else:
                buf = bytearray()
                for y in range(size):
                    for x in range(size):
                        o = (y*TILE + x)*3
                        buf.extend(d[o:o+3])
                out = bytes(buf)
            with open(os.path.join(base, f'thr_{ink}.bin'), 'wb') as f:
                f.write(out)
            chans.append(dict(ink=ink, file=f'thr_{ink}.bin', content_top_page_row=TOP[ink], approx=False))
        meta = dict(
            version=4, size=size, tile_size=TILE,
            engine_rule='level(v,x,y) = (v>=T1)+(v>=T2)+(v>=T3); thr_<ink>.bin = size*size*3 bytes [T1,T2,T3] uint8 raster order y*size+x; 0 = never',
            coordinate_indexing=dict(type='content-relative',
                                     evidence='D(x,y)=TILE[x%1024][y%1024]; margin experiment 100% match at same content coords'),
            tile=dict(size=TILE, evidence='probe_scan_C64_720: lag-1024 level equality 100.000% in x and y'),
            channels=chans,
            decoder_convention='ESC/P2 2bit MSB-first; prow = pos_k + 8*r - content_top; nonzero merge; identical to tools/validate/validate_e2e.py::decode_page',
            source='probe_scan_{C,M,Y,K}###_176 (256 levels each, 176x176 CMYK probe, A3-DTF-1390.prs modeId=2)',
            contact='prs-analyst')
        with open(os.path.join(base, 'screen_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
    write_set(REF, TILE); write_set(ENG, TILE); write_set(BUILD, TILE); write_set(LEG, 384)
    print('written: build/screen, reference/screen, reference/screen/engine (1024); reference/screen/legacy384 (384)')
    # validation
    def val(ink, tone, content):
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{tone:03d}' + ('_176' if content > 1000 else '') + '_a3dtf1390_m2.prn')
        if not os.path.exists(fn): return None
        cv = V.decode_page(fn, content=content).get(COLOR[ink])
        if cv is None: return None
        d = tiles[ink]
        N = min(content, TILE)
        mism = 0
        for y in range(N):
            row = cv[y]
            base = y*TILE*3
            for x in range(N):
                o = base + x*3
                T1, T2, T3 = d[o], d[o+1], d[o+2]
                pred = (1 if tone >= T1 > 0 else 0) + (1 if tone >= T2 > 0 else 0) + (1 if tone >= T3 > 0 else 0)
                if pred != row[x]: mism += 1
        return (N*N-mism)*100.0/(N*N)
    allworst = 100.0
    for label, content in (('64px probes (content=384)', 384), ('176px probes (content=1056, region 1024)', 1056)):
        print(f'\n=== validation under lead decoder: {label} ===')
        for ink in ('C', 'M', 'Y', 'K'):
            cw = 100.0
            for t in TONES:
                a = val(ink, t, content)
                if a is None: continue
                cw = min(cw, a)
            print(f'  {ink}: worst={cw:.4f}%')
            allworst = min(allworst, cw)
    print(f'\nworst overall = {allworst:.4f}%')
    # save validation report
    with open(os.path.join(REF, 'screen_validation.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(worst_overall=allworst,
                       note='predict level from thr_{C,M,Y,K}.bin at content coords, compare with lead decoder decode_page',
                       tones=list(TONES)), f, indent=1)

if __name__ == '__main__':
    main()
