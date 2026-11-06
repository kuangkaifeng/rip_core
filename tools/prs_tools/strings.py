#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dump printable strings (minlen configurable) in all/range of file, with gaps shown."""
import sys, re

def dump(fn, lo=0, hi=None, minlen=3, maxlen=400):
    d = open(fn, 'rb').read()
    if hi is None: hi = len(d)
    pat = re.compile(rb'[\x20-\x7e]{%d,}' % minlen)
    for m in pat.finditer(d):
        o = m.start()
        if lo <= o < hi:
            s = m.group().decode('latin1')
            print(f'{o:06X} {s[:maxlen]}')

if __name__ == '__main__':
    fn = sys.argv[1]
    lo = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3], 0) if len(sys.argv) > 3 else None
    minlen = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    dump(fn, lo, hi, minlen)
