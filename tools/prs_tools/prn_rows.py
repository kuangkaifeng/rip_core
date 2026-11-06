#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Visualize first rows of each color record of a block (2-bit dot values as chars 0-3)."""
import sys, os, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"

def load():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]

def rowstr(raw, row, nbytes):
    chunk = raw[row*nbytes:(row+1)*nbytes]
    s = []
    for b in chunk:
        s.extend(UNPACK[b])
    return ''.join(str(v) for v in s)

def main(fn, block=0, rows=(0,1,40,80)):
    P = load()
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    blk = job.blocks[block]
    print(f'{os.path.basename(fn)} block {block} advance={blk.advance}')
    for r in blk.records:
        if r.raw is None:
            print(f'color 0x{r.color:02X}: no data'); continue
        print(f'-- color 0x{r.color:02X} xpos={r.xpos} n={r.n} --')
        for row in rows:
            print('   r%3d: %s' % (row, rowstr(r.raw, row, r.n)))

if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
