#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Print double arrays at given offsets in a .prs."""
import sys, struct

def main(fn, bases, n=48):
    d = open(fn, 'rb').read()
    def f64(o): return struct.unpack_from('<d', d, o)[0]
    for b in bases:
        b = int(b, 0)
        print(f'--- doubles @0x{b:X} first {n} ---')
        vals = [f64(b + 8*i) for i in range(n)]
        print(', '.join(f'{v:.6f}' for v in vals))

if __name__ == '__main__':
    fn = sys.argv[1]
    bases = sys.argv[2:]
    main(fn, bases)
