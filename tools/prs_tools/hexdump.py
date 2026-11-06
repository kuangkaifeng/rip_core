#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hexdump a range of a file with ascii column, optional repeated-line folding."""
import sys, struct

def hexdump(d, off, n, base=0, fold=True):
    lines = []
    prev = None
    prev_off = None
    run = 1
    for i in range(0, n, 16):
        chunk = d[off+i:off+i+16]
        if not chunk: break
        hexs = ' '.join(f'{b:02X}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        if fold and chunk == prev:
            run += 1
            continue
        if run > 1:
            lines.append(f'        ... repeated x{run} ...')
            run = 1
        lines.append(f'{base+off+i:08X}  {hexs:<48}  {asc}')
        prev = bytes(chunk)
    if run > 1:
        lines.append(f'        ... repeated x{run} ...')
    print('\n'.join(lines))

if __name__ == '__main__':
    fn = sys.argv[1]
    d = open(fn, 'rb').read()
    lo = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3], 0) if len(sys.argv) > 3 else min(lo+512, len(d))
    fold = (sys.argv[4] != 'nofold') if len(sys.argv) > 4 else True
    hexdump(d, lo, hi-lo, fold=fold)
