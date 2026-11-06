#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Visualize a plane raster region as ASCII + horizontal period estimate (halftone screen analysis)."""
import sys, os, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

def load():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def rows_of(raw, nbytes):
    out=[]
    for r in range(len(raw)//nbytes):
        chunk = raw[r*nbytes:(r+1)*nbytes]
        row=[]
        for b in chunk: row.extend(UNPACK[b])
        out.append(row)
    return out

def find_content(rows):
    ys=[]
    for i,row in enumerate(rows):
        if any(row): ys.append(i)
    return (min(ys), max(ys)) if ys else (0,0)

def autocorr_period(row, maxlag=40):
    n=len(row)
    mean=sum(row)/n
    x=[v-mean for v in row]
    best=[]
    for lag in range(2, maxlag):
        s=sum(x[i]*x[i+lag] for i in range(n-lag))/(n-lag)
        best.append((s,lag))
    best.sort(reverse=True)
    return best[:6]

def main(fn, color, block=20):
    P = load()
    d=open(fn,'rb').read()
    job=P.parse_job(d, decode=True)
    print(f'{os.path.basename(fn)} blocks={len(job.blocks)}')
    # collect records of given color across blocks
    recs=[r for b in job.blocks for r in b.records if r.color==color and r.raw]
    print(f'color 0x{color:02X}: {len(recs)} records with data')
    if not recs: return
    # use the record with most nonzero rows
    best=max(recs, key=lambda r: sum(1 for i in range(r.m) if any(r.raw[i*r.n:(i+1)*r.n])))
    rows=rows_of(best.raw, best.n)
    y0,y1=find_content(rows)
    print(f'chosen record xpos={best.xpos} content rows {y0}..{y1} n={best.n}')
    # ASCII art 64 dots wide starting at first nonzero col
    for r in range(y0, min(y0+24, y1+1)):
        row=rows[r]
        s=''.join('.' if v==0 else str(v) for v in row[:80])
        print(f'  r{r:3d} {s}')
    # periodicity on a dense row
    dense=max(rows[y0:y1+1], key=lambda row: sum(1 for v in row if v))
    print('autocorr top lags:', autocorr_period([v>0 for v in dense]))
    # vertical periodicity: column profile
    col=[0]*len(rows[0])
    for r in range(y0, y1+1):
        for i,v in enumerate(rows[r]):
            if v: col[i]+=1
    print('content cols: first/last nonzero', next((i for i,v in enumerate(col) if v), None),
          max((i for i,v in enumerate(col) if v), default=None))

if __name__=='__main__':
    fn=sys.argv[1]; color=int(sys.argv[2],0)
    main(fn,color)
