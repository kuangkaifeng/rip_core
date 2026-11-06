#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Diff two files: report differing regions (merged), with hexdump context."""
import sys

def regions(a, b, gap=8):
    n = min(len(a), len(b))
    diffs = []
    i = 0
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            diffs.append((i, j))
            i = j
        else:
            i += 1
    # merge close regions
    merged = []
    for s, e in diffs:
        if merged and s - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append([s, e])
    return merged

def main():
    fa, fb = sys.argv[1], sys.argv[2]
    a = open(fa, 'rb').read(); b = open(fb, 'rb').read()
    print(f'A={fa} ({len(a)})  B={fb} ({len(b)})  delta={len(b)-len(a)}')
    rs = regions(a, b)
    print(f'{len(rs)} differing regions (merged, gap=8)')
    for s, e in rs[:200]:
        print(f'@{s:08X}..{e:08X} len={e-s}')
        print(f'   A: {a[s:min(e,s+96)].hex(" ")}')
        print(f'   B: {b[s:min(e,s+96)].hex(" ")}')
        try:
            print(f'   Aasc: {a[s:min(e,s+96)].decode("latin1")!r}')
            print(f'   Basc: {b[s:min(e,s+96)].decode("latin1")!r}')
        except Exception:
            pass

if __name__ == '__main__':
    main()
