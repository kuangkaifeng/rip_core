#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diff two .prn files: report differing offset ranges + printable context."""
import sys


def ranges(path):
    a = open(sys.argv[1], "rb").read()
    b = open(sys.argv[2], "rb").read()
    print(f"A={sys.argv[1]} len={len(a)}")
    print(f"B={sys.argv[2]} len={len(b)}")
    if len(a) != len(b):
        print("LENGTHS DIFFER")
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
    print(f"diff bytes in {len(diffs)} ranges")
    total = sum(j - i for i, j in diffs)
    print(f"total differing bytes: {total} / {n} ({100.0*total/n:.4f}%)")
    for i, j in diffs[:40]:
        print(f"  @{i:9d}..{j:9d} len={j-i:6d}")
    if len(diffs) > 40:
        print(f"  ... ({len(diffs)-40} more ranges)")
    if diffs:
        lo = diffs[0][0]
        hi = diffs[-1][1]
        print(f"first diff @{lo} last diff end @{hi}")
        # context
        for i, j in diffs[:8]:
            ctxt = a[max(0, i-32):j+32]
            print(f"\nA ctx @{max(0,i-32)}: {ctxt!r}")
            print(f"B ctx @{max(0,i-32)}: {b[max(0,i-32):j+32]!r}")


if __name__ == "__main__":
    ranges(sys.argv[1])
