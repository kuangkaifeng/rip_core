#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze white-ink / mode semantics of A3-DTF-1390 PRNs.

For each PRN: list raster records (color code, n, m), blocks/advances, and per-record
ink coverage (nonzero dots, level sum) over content page rows, so we can tell:
  - mode2 (4 records, no W planes) ignores inputColorEditor W1/W2
  - mode1/3/5/7 (6 records) carry W1/W2 planes, and whether they are full-page or
    content-only.
"""
import os, sys, json, importlib.util
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
PARSE = os.path.join(ROOT, 'tools', 'prn_tools', 'parse_prn.py')
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]
NAMES = {0x00: '0x00', 0x01: '0x01', 0x02: '0x02', 0x04: '0x04', 0x11: '0x11', 0x12: '0x12'}

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def analyze(P, path):
    d = open(path, 'rb').read()
    job = P.parse_job(d, decode=True)
    recs = {}
    per_color = {}
    pos = 0
    adv = []
    for bi, blk in enumerate(job.blocks):
        if blk.advance is not None:
            pos += blk.advance
            if bi > 0:
                adv.append(blk.advance)
        for rec in blk.records:
            if not rec.raw:
                continue
            key = rec.color
            nz = 0; lsum = 0; rows_nz = []
            for r in range(rec.m):
                chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                row_nz = 0
                for b in chunk:
                    for v in UNPACK[b]:
                        if v:
                            nz += 1; lsum += v; row_nz += 1
                if row_nz:
                    rows_nz.append((pos + 8*r, row_nz))
            per_color.setdefault(key, dict(nz=0, lsum=0, page_rows=set()))
            per_color[key]['nz'] += nz
            per_color[key]['lsum'] += lsum
            for (pr, c) in rows_nz:
                per_color[key]['page_rows'].add(pr)
    out = dict(file=os.path.basename(path), blocks=len(job.blocks),
               advances=dict(unique=sorted(set(adv)) if adv else [], n=len(adv)),
               colors={})
    for code, v in per_color.items():
        prs = v['page_rows']
        out['colors'][NAMES.get(code, hex(code))] = dict(
            nonzero_dots=v['nz'], level_sum=v['lsum'],
            page_row_min=min(prs) if prs else None,
            page_row_max=max(prs) if prs else None,
            page_rows=len(prs))
    return out

def main():
    files = sys.argv[1:]
    if not files:
        files = [
            'a3dtf1390_flat_black_100_m2_golden.prn',
            'print_debug_white_m2_iceW1full_black.prn',
            'print_debug_white_m3_iceW1full_black.prn',
            'print_debug_white_m3_iceW1color_alpha.prn',
            'a3dtf1390_flat_black_100_m3_golden.prn',
            'a3dtf1390_flat_black_100_m3_w1w2.prn',
            'a3dtf1390_cmyk_quad_100_m3_w1w2.prn',
            'exp_a3_white_matrix_ice_m3_cmykquad_rt1_tw0.prn',
        ]
    P = load_parser()
    report = []
    for fn in files:
        p = os.path.join(SAMPLES, fn) if not os.path.isabs(fn) else fn
        if not os.path.exists(p):
            print(fn, 'MISSING'); continue
        try:
            r = analyze(P, p)
        except Exception as e:
            print(fn, 'ERROR', e); continue
        report.append(r)
        print('=' * 100)
        print('FILE', r['file'], '| blocks', r['blocks'], '| advances', r['advances'])
        for code, v in sorted(r['colors'].items()):
            print(f"  color {code}: nz_dots={v['nonzero_dots']:8d} level_sum={v['level_sum']:9d}"
                  f" page_rows={v['page_rows']} range=[{v['page_row_min']},{v['page_row_max']}]")
    with open(os.path.join(ROOT, 'work', 'prs', 'white_mode_analysis.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    print('\nsaved work/prs/white_mode_analysis.json')

if __name__ == '__main__':
    main()
