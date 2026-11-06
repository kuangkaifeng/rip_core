#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scan .prs for path records and mode blocks."""
import sys, re, os, json

BIN = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin"
FILES = [
    r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\A3-DTF-1390.prs",
    os.path.join(BIN, 'H13 XP600.prs'),
    os.path.join(BIN, 'H13 XP600_myicc.prs'),
    os.path.join(BIN, 'test_my.prs'),
    os.path.join(BIN, 'test_bare.prs'),
    os.path.join(BIN, 'test_wrong.prs'),
]

PAT = re.compile(rb'[\x21-\x7e][\x20-\x7e]{2,}(?:\.icc|\.icm|\.mcm|\.pdv|\.wpk)\x00', re.I)

def scan(fn):
    d = open(fn, 'rb').read()
    print('=' * 100)
    print(f'{os.path.basename(fn)} size={len(d)} (0x{len(d):X})')
    hits = [(m.start(), m.group()[:-1].decode('latin1')) for m in PAT.finditer(d)]
    for off, s in hits:
        # find actual string start (could be preceded by path chars)
        print(f'  {off:06X} {s}')
    # find path-like runs then show record start = off - (align)
    return d

def tail_struct(fn):
    d = open(fn, 'rb').read()
    print('=' * 100)
    print(f'{os.path.basename(fn)} size={len(d)}')
    # last 6000 bytes as hex words
    lo = max(0, len(d) - 5000)
    print(f'-- last 5000 bytes, u32 words at 16/line from 0x{lo:X} --')
    for off in range(lo, len(d), 64):
        chunk = d[off:off+64]
        words = [f'{int.from_bytes(chunk[i:i+4], "little"):08X}' for i in range(0, len(chunk), 4) if len(chunk[i:i+4]) == 4]
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'{off:06X}  ' + ' '.join(words) + '  |' + asc + '|')

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    files = sys.argv[2:] or FILES
    for fn in files:
        if mode == 'scan': scan(fn)
        else: tail_struct(fn)
