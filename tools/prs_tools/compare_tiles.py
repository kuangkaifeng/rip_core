#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compare screen tile payloads under lead's decoder; report per-channel accuracy,
holes, and build a merged best-of payload.
Candidates:
  A = reference/screen/engine     (prs-analyst: direct 176x256-scan extraction)
  B = reference/screen/engine1024 (lead: built from T1 D bins)
Metric: predict level from tile vs oracle decode_page at probe tones (64px/176px probes).
"""
import os, sys, json, importlib.util, collections
ROOT = r"D:\work\RIP核心分析"
REF = os.path.join(ROOT, 'reference', 'screen')
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
TILE = 1024
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TONES = (0, 16, 64, 128, 192, 240, 255)

def load_decoder():
    spec = importlib.util.spec_from_file_location("validate_e2e", os.path.join(ROOT, 'tools', 'validate', 'validate_e2e.py'))
    V = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(V)
    except SystemExit:
        pass
    return V

def load_tile(dirpath):
    return {ink: open(os.path.join(dirpath, f'thr_{ink}.bin'), 'rb').read() for ink in COLOR}

def acc(V, tiles, ink, content):
    d = tiles[ink]
    worst = 100.0
    for t in TONES:
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{t:03d}' + ('_176' if content > 1000 else '') + '_a3dtf1390_m2.prn')
        if not os.path.exists(fn):
            continue
        cv = V.decode_page(fn, content=content).get(COLOR[ink])
        if cv is None:
            continue
        N = min(content, TILE)
        mism = 0
        for y in range(N):
            row = cv[y]
            for x in range(N):
                o = (y*TILE + x)*3
                T1, T2, T3 = d[o], d[o+1], d[o+2]
                pred = (1 if T1 and t >= T1 else 0) + (1 if T2 and t >= T2 else 0) + (1 if T3 and t >= T3 else 0)
                if pred != row[x]:
                    mism += 1
        worst = min(worst, (N*N-mism)*100.0/(N*N))
    return worst

def fill_holes(tile, method='cyclic'):
    """Fill T1==0 pixels from cyclic neighbours (x+1) so engine never sees a hole."""
    out = bytearray(tile)
    S = TILE
    holes = [(i//S, i%S) for i in range(S*S) if out[i*3] == 0]
    for (y, x) in holes:
        # search nearest neighbour with valid thresholds (cyclic)
        for r in range(1, 32):
            cand = [((y+r) % S, x), (y, (x+r) % S), ((y-r) % S, x), (y, (x-r) % S)]
            done = False
            for yy, xx in cand:
                o = (yy*S + xx)*3
                if out[o]:
                    oo = (y*S+x)*3
                    out[oo] = out[o]; out[oo+1] = out[o+1]; out[oo+2] = out[o+2]
                    done = True; break
            if done: break
    return bytes(out), len(holes)

def main():
    V = load_decoder()
    paths = {'A_mine': os.path.join(REF, 'engine'), 'B_lead': os.path.join(REF, 'engine1024')}
    tiles = {}
    for tag, p in paths.items():
        try:
            tiles[tag] = load_tile(p)
        except FileNotFoundError as e:
            print(f'{tag}: missing ({e})')
    print('=== holes (T1==0 pixels) ===')
    for tag, T in tiles.items():
        print(f'  {tag}: ' + ', '.join(f'{ink}={sum(1 for i in range(TILE*TILE) if T[ink][i*3]==0)}' for ink in COLOR))
    print('\n=== accuracy under lead decoder ===')
    best = {}
    for content in (384, 1056):
        print(f'-- content={content}')
        for ink in ('C', 'M', 'Y', 'K'):
            row = []
            for tag in tiles:
                a = acc(V, tiles[tag], ink, content)
                row.append(f'{tag}={a:.4f}%')
                if tag not in best: best[tag] = {}
                best[tag][(ink, content)] = a
            print(f'  {ink}: ' + '  '.join(row))
    # merged: choose per-channel per-content... but tile must be one file per channel:
    # criterion = average over the two contents; prefer A unless B strictly better by >0.01%
    print('\n=== merged best-of (per channel, avg of content 384/1056) ===')
    merged = {}
    srcs = {}
    for ink in ('C', 'M', 'Y', 'K'):
        avg = {tag: (best[tag][(ink, 384)] + best[tag][(ink, 1056)]) / 2 for tag in tiles}
        pick = max(avg, key=avg.get)
        srcs[ink] = (pick, avg)
        merged[ink] = tiles[pick][ink]
        print(f'  {ink}: ' + '  '.join(f'{tag}={avg[tag]:.4f}' for tag in avg) + f'  -> {pick}')
    # fill holes in merged (except when holes are beneficial? use cyclic fill; report cost)
    print('\n=== hole filling (cyclic neighbour) ===')
    filled = {}
    for ink in ('C', 'M', 'Y', 'K'):
        t, n = fill_holes(merged[ink])
        filled[ink] = t
        print(f'  {ink}: filled {n} holes')
    # evaluate filled variant
    print('\n=== filled variant accuracy ===')
    for content in (384, 1056):
        for ink in ('C', 'M', 'Y', 'K'):
            a = acc(V, filled, ink, content)
            print(f'  content={content} {ink}: {a:.4f}%')
    # write final payload
    final = os.path.join(REF, 'final')
    os.makedirs(final, exist_ok=True)
    for ink in ('C', 'M', 'Y', 'K'):
        open(os.path.join(final, f'thr_{ink}.bin'), 'wb').write(filled[ink])
        # D for reference
        D = bytearray()
        for i in range(TILE*TILE):
            t1, t2, t3 = filled[ink][i*3], filled[ink][i*3+1], filled[ink][i*3+2]
            lo, hi = 0, 255
            if t1: lo = max(lo, 256-3*t1); hi = min(hi, 258-3*t1)
            if t2: lo = max(lo, 512-3*t2); hi = min(hi, 514-3*t2)
            if t3: lo = max(lo, 768-3*t3); hi = min(hi, 770-3*t3)
            D.append(max(0, min(255, round((lo+hi)/2))))
        open(os.path.join(final, f'D_{ink}.bin'), 'wb').write(D)
    meta = dict(
        version=5, size=TILE, tile_size=TILE,
        engine_rule='level(v,x,y) = (v>=T1)+(v>=T2)+(v>=T3); thr_<ink>.bin = size*size*3 bytes [T1,T2,T3] uint8 raster order y*size+x; 0=never',
        coordinate_indexing=dict(type='content-relative', tile_indexing='D(x,y)=TILE[x%1024][y%1024]'),
        channels=[dict(ink=ink, file=f'thr_{ink}.bin',
                       content_top_page_row=640 if ink in ('C', 'K') else 644,
                       source=('prs-analyst direct 176x256-scan extraction' if srcs[ink][0] == 'A_mine' else 'lead build_tile1024_from_D'),
                       holes_filled=True) for ink in ('C', 'M', 'Y', 'K')],
        decoder_convention='ESC/P2 2bit MSB-first; prow = pos_k + 8*r - content_top; nonzero merge; identical to tools/validate/validate_e2e.py::decode_page',
        validation='probe tones {0,16,64,128,192,240,255}: per-channel accuracy listed in work/prs/compare_tiles.log')
    json.dump(meta, open(os.path.join(final, 'screen_meta.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'\nfinal merged payload written: {final}')

if __name__ == '__main__':
    main()
