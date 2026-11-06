#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit oracle probe PRNs for self-inconsistency (non-monotone level vs tone) at the
candidate pixels: all tile pixels with T3==0 (D<3, i.e. level can never reach 3).

For each such (ink, content pixel), read the raw 2-bit dot from all 256 tone PRNs
(direct byte access, no canvas) and report tones where the level breaks monotonicity.
"""
import os, sys, json, collections, importlib.util
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
SCREEN = os.path.join(ROOT, 'reference', 'screen', 'final')
TILE = 1024
PARSE = os.path.join(ROOT, 'tools', 'prn_tools', 'parse_prn.py')
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def parser_index_for_page_row(P, page_row, rows_info):
    """Return list of (block_idx, raster_row) whose mapped page row equals page_row."""
    return rows_info.get(page_row, [])

def build_row_index(P, fn, color):
    """map page_row -> list of (block_pos, raster_row) for one PRN."""
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    pos = 0; idx = {}
    for blk in job.blocks:
        if blk.advance is not None: pos += blk.advance
        for rec in blk.records:
            if rec.color != color or not rec.raw: continue
            for r in range(rec.m):
                idx.setdefault(pos + 8*r, []).append((pos, r, rec))
    return idx

def main():
    P = load_parser()
    # candidate pixels: content coords where T3==0
    cands = {}
    for ink in 'CMYK':
        d = open(os.path.join(SCREEN, f'thr_{ink}.bin'), 'rb').read()
        pts = [(i//TILE, i % TILE) for i in range(TILE*TILE) if d[i*3+2] == 0]
        cands[ink] = pts
        print(f'{ink}: T3==0 pixels = {len(pts)}')
    # for each ink scan all tones at these points
    report = {}
    for ink, pts in cands.items():
        if not pts: continue
        code = COLOR[ink]; top = TOP[ink]
        # map content y -> page row
        series = {pt: [] for pt in pts}
        t0 = 255
        for tone in range(1, 256):
            fn = os.path.join(SAMPLES, f'probe_scan_{ink}{tone:03d}_176_a3dtf1390_m2.prn')
            if not os.path.exists(fn):
                continue
            d = open(fn, 'rb').read()
            job = P.parse_job(d, decode=True)
            pos = 0
            # collect needed rows only
            need_rows = {}  # page_row -> list of content ys
            for (y, x) in pts:
                need_rows.setdefault(top + y, []).append(y)
            got = {}
            for blk in job.blocks:
                if blk.advance is not None: pos += blk.advance
                for rec in blk.records:
                    if rec.color != code or not rec.raw: continue
                    for r in range(rec.m):
                        pr = pos + 8*r
                        ys = need_rows.get(pr)
                        if not ys: continue
                        chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                        for (y, x) in pts:
                            if top + y != pr: continue
                            bi = x >> 2
                            if bi < len(chunk):
                                v = (chunk[bi] >> (6 - 2*(x & 3))) & 3
                                if v: got[(y, x)] = max(got.get((y, x), 0), v)
            for pt in pts:
                series[pt].append((tone, got.get(pt, 0)))
        # non-monotone analysis
        bad = {}
        for pt, seq in series.items():
            viol = []
            mx = 0
            for tone, lv in seq:
                if lv < mx:
                    viol.append((tone, lv, mx))
                mx = max(mx, lv)
            if viol:
                bad[pt] = viol
        print(f'\n{ink}: {len(bad)}/{len(pts)} pixels have non-monotone oracle series')
        for pt, viol in list(bad.items())[:10]:
            print(f'  content(y={pt[0]},x={pt[1]}): {len(viol)} violations, e.g. {viol[:6]}')
        report[ink] = {f'{pt[0]},{pt[1]}': viol for pt, viol in bad.items()}
    with open(os.path.join(ROOT, 'work', 'prs', 'oracle_screen_audit.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=1)
    print('\nsaved work/prs/oracle_screen_audit.json')

if __name__ == '__main__':
    main()
