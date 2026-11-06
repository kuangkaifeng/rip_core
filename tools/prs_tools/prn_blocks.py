#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Print detailed record table for the first blocks of an ESC/P2 PRN."""
import sys, os, importlib.util
PARSE = r"D:\work\RIP核心分析\tools\prn_tools\parse_prn.py"

def load():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def main(fn, nblocks=2):
    P = load()
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=False)
    print(f'{os.path.basename(fn)}: blocks={len(job.blocks)} size={len(d)}')
    for blk in job.blocks[:nblocks]:
        print(f'-- block {blk.index} advance={blk.advance} --')
        for r in blk.records:
            print(f'   color=0x{r.color:02X} comp={r.comp} bit={r.bit} n={r.n} m={r.m} xpos={r.xpos} off=0x{r.offset:X} len={r.data_len}')
    # last block
    if len(job.blocks) > nblocks:
        blk = job.blocks[-1]
        print(f'-- last block {blk.index} advance={blk.advance} --')
        for r in blk.records:
            print(f'   color=0x{r.color:02X} n={r.n} xpos={r.xpos} len={r.data_len}')

if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2)
