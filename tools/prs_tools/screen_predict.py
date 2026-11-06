#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""screen_predict.py -- MainTop A3-DTF-1390 mode2 halftone (screen) predictor.

Model (verified):
    level(v,x,y) = (v >= T1) + (v >= T2) + (v >= T3)      v = device ink 0..255
    (x,y) = CONTENT coordinates in device dots (720dpi, mode2)
    thr_<ink>.bin from reference/screen (canonical) or build/screen:
      size*size*3 bytes [T1,T2,T3] per pixel, raster order y*size+x, 0 = never.
    Threshold field = 1024x1024 tile, content-relative:
      D(x,y) = TILE[x % 1024][y % 1024]
    Current payload: size=1024 => complete tile known exactly for all 4 inks.

Decoder convention (identical to tools/validate/validate_e2e.py::decode_page):
    ESC/P2 2bit MSB-first; prow = pos_k + 8*raster_row - content_top;
    content_top: C/K=640, M/Y=644 (A3 mode2, 120dpi input).

Usage:
  python tools/prs_tools/screen_predict.py validate        # probe PRN acceptance
  python tools/prs_tools/screen_predict.py show C 64       # 8x32 level view
  python tools/prs_tools/screen_predict.py plane C 128 --out plane_C128.bin
"""
import os, sys, argparse, json

ROOT = r"D:\work\RIP核心分析"
SCREEN = os.path.join(ROOT, 'reference', 'screen')
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}
VSTEP = 8
TILE = 1024

def load_decoder():
    import importlib.util
    spec = importlib.util.spec_from_file_location("validate_e2e", os.path.join(ROOT, 'tools', 'validate', 'validate_e2e.py'))
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m

class Screen:
    def __init__(self, base=None):
        self.base = base or SCREEN
        meta_path = os.path.join(self.base, 'screen_meta.json')
        self.meta = json.load(open(meta_path, encoding='utf-8')) if os.path.exists(meta_path) else {}
        self.size = self.meta.get('size', TILE)
        self.thr = {}
        for ink in COLOR:
            fn = os.path.join(self.base, f'thr_{ink}.bin')
            d = open(fn, 'rb').read()
            if len(d) != self.size*self.size*3:
                raise SystemExit(f'{fn}: size={len(d)} expect {self.size*self.size*3}')
            self.thr[ink] = d

    def level(self, ink, v, x, y):
        if not (0 <= x < self.size and 0 <= y < self.size):
            raise IndexError(f'({x},{y}) outside known tile {self.size}')
        o = (y*self.size + x)*3
        T = self.thr[ink]
        return ((1 if T[o] and v >= T[o] else 0) + (1 if T[o+1] and v >= T[o+1] else 0)
                + (1 if T[o+2] and v >= T[o+2] else 0))

    def plane(self, ink, v):
        T = self.thr[ink]
        out = bytearray(self.size*self.size)
        o = 0
        for i in range(len(out)):
            out[i] = ((1 if T[o] and v >= T[o] else 0) + (1 if T[o+1] and v >= T[o+1] else 0)
                      + (1 if T[o+2] and v >= T[o+2] else 0))
            o += 3
        return out

def validate():
    V = load_decoder()
    scr = Screen()
    print(f'screen tile size={scr.size} (meta version={scr.meta.get("version")})')
    tones = (0, 16, 64, 128, 192, 240, 255)
    worst = 100.0
    for ink in ('C', 'M', 'Y', 'K'):
        d = scr.thr[ink]
        cw = 100.0
        for content, suffix in ((384, ''), (1056, '_176')):
            for t in tones:
                fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}{suffix}_a3dtf1390_m2.prn')
                if not os.path.exists(fn):
                    continue
                cv = V.decode_page(fn, content=content).get(COLOR[ink])
                if cv is None:
                    continue
                N = min(content, scr.size)
                mism = 0
                for y in range(N):
                    row = cv[y]
                    for x in range(N):
                        o = (y*scr.size + x)*3
                        T1, T2, T3 = d[o], d[o+1], d[o+2]
                        pred = ((1 if T1 and t >= T1 else 0) + (1 if T2 and t >= T2 else 0)
                                + (1 if T3 and t >= T3 else 0))
                        if pred != row[x]:
                            mism += 1
                acc = (N*N-mism)*100.0/(N*N)
                cw = min(cw, acc)
                print(f'  {ink} content={content} tone {t:3d}: {acc:.4f}%')
        print(f'  {ink}: worst={cw:.4f}%')
        worst = min(worst, cw)
    print(f'worst overall = {worst:.4f}%')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['validate', 'show', 'plane'])
    ap.add_argument('ink', nargs='?', choices=list(COLOR))
    ap.add_argument('value', nargs='?', type=int)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    if args.cmd == 'validate':
        validate()
    elif args.cmd == 'show':
        scr = Screen()
        for y in range(8):
            print(''.join(str(scr.level(args.ink, args.value, x, y)) for x in range(32)))
    elif args.cmd == 'plane':
        scr = Screen()
        data = scr.plane(args.ink, args.value)
        if args.out:
            open(args.out, 'wb').write(data)
            print(f'wrote {args.out} ({len(data)} bytes)')
        else:
            print(len(data))

if __name__ == '__main__':
    main()
