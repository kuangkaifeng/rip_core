#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Decode a probe ESC/P2 PRN into a page-space 2-bit canvas.

Geometry (docs/02_geometry_escp2.md, verified by Lead):
  - A3 mode2 page unit = 720/in => 1 page unit == 1 dot for mode2
  - block k rows: page_row = pos_k + VSTEP*r, VSTEP = 8 for mode2
  - n = bytes per raster row, m = 90 rows, 2bit MSB-first, 4 dots/byte
Canvas is (H, W): H = max pos + VSTEP*m, W = n*4.
"""
import sys, os, struct, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
UNPACK_MSB = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]
UNPACK_LSB = [(b & 3, (b >> 2) & 3, (b >> 4) & 3, (b >> 6) & 3) for b in range(256)]
UNPACK = UNPACK_LSB if os.environ.get('PRN_UNPACK', 'lsb') == 'lsb' else UNPACK_MSB
VSTEP = {'m0': 4, 'm1': 4, 'm2': 8, 'm3': 8, 'm5': 24, 'm7': 24, 'm9': 24}

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def prologue_map(P, job):
    return P.prologue_map(job)

def decode_canvas(fn, vstep=8, verbose=False):
    P = load_parser()
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    pm = P.prologue_map(job)
    # positions
    pos = 0
    blocks = []
    for b in job.blocks:
        if b.advance is not None:
            pos += b.advance
        blocks.append((pos, b))
    W = 0
    H = 0
    for p, b in blocks:
        for r in b.records:
            W = max(W, r.n * 4)
        H = max(H, p + vstep * (max(r.m for r in b.records) - 1))
    canvases = {}
    overlaps = 0
    for p, b in blocks:
        for r in b.records:
            if not r.raw:
                continue
            cv = canvases.get(r.color)
            if cv is None:
                cv = [[0]*W for _ in range(H)]
                canvases[r.color] = cv
            for row in range(r.m):
                pr = p + vstep*row
                if pr >= H: break
                chunk = r.raw[row*r.n:(row+1)*r.n]
                out = cv[pr]
                x = 0
                for byte in chunk:
                    u = UNPACK[byte]
                    for k in range(4):
                        if x >= W: break
                        if u[k]:
                            if out[x]:
                                overlaps += 1
                            else:
                                out[x] = u[k]
                        x += 1
    if verbose:
        print(f'{os.path.basename(fn)}: blocks={len(blocks)} W={W} H={H} overlaps={overlaps}')
        print(f'  prologue: ESC_D={pm.get("ESC_D")} ESC_S={pm.get("ESC_S")} ESC_c={pm.get("ESC_c")} ESC_e={pm.get("ESC_e")} ESC_K={pm.get("ESC_K")}')
        print(f'  advances: {[b.advance for _, b in blocks][:20]}...')
        print(f'  records per block: {[len(b.records) for _, b in blocks][:5]}')
    return canvases, dict(W=W, H=H, overlaps=overlaps, prologue=pm,
                         blocks=[(p, b.advance, [(r.color, r.n, r.m, r.xpos) for r in b.records]) for p, b in blocks])

if __name__ == '__main__':
    for fn in sys.argv[1:]:
        decode_canvas(fn, vstep=int(os.environ.get('VSTEP', '8')), verbose=True)
