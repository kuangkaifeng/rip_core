#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze probe canvas: content region, row/col mapping, level stats for C probes."""
import sys, os, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
import prn_canvas

def analyze(fn, color, tone):
    cvs, info = prn_canvas.decode_canvas(fn, vstep=8, verbose=False)
    cv = cvs.get(color)
    if cv is None:
        print(f'{os.path.basename(fn)}: color 0x{color:02X} absent'); return None
    W, H = info['W'], info['H']
    nz_rows = [y for y in range(H) if any(cv[y])]
    nz_cols = collections.Counter()
    for y in range(H):
        for x in range(W):
            if cv[y][x]: nz_cols[x] += 1
    cols = sorted(nz_cols)
    print(f'{os.path.basename(fn)} tone={tone}: size={W}x{H} content rows {min(nz_rows)}..{max(nz_rows)} '
          f'({len(nz_rows)} rows), cols {min(cols)}..{max(cols)}')
    # row gaps
    gaps = [(nz_rows[i], nz_rows[i+1]) for i in range(len(nz_rows)-1) if nz_rows[i+1]-nz_rows[i] > 1]
    print(f'  row gaps (>1): {gaps[:20]} (total {len(gaps)})')
    # per-row nonzero count distribution & level hist
    hist = [0,0,0,0]
    rowcounts = []
    for y in nz_rows:
        row = cv[y]
        c = 0
        for x in cols:
            v = row[x]
            hist[v] += 1
            if v: c += 1
        rowcounts.append(c)
    print(f'  level hist in content: {hist}  -> mean={sum(i*hist[i] for i in range(4))/max(1,sum(hist)):.3f}')
    print(f'  rowcount min/max/avg: {min(rowcounts) if rowcounts else 0}/{max(rowcounts) if rowcounts else 0}/'
          f'{sum(rowcounts)/max(1,len(rowcounts)):.1f}')
    return cvs, info, (min(nz_rows), max(nz_rows), min(cols), max(cols))

if __name__ == '__main__':
    for fn in sys.argv[1:]:
        # filename pattern: probe_screen_probe_C64_a3dtf1390_m2.prn
        base = os.path.basename(fn)
        ch = base.split('_')[3][0]
        tone = int(base.split('_')[3][1:])
        color = {'C':0x00,'K':0x04,'M':0x12,'Y':0x11}[ch]
        analyze(fn, color, tone)
