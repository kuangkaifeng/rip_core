# -*- coding: utf-8 -*-
import struct, collections
WS = r"D:\work\RIP核心分析"
def planes(d):
    h = struct.unpack("<12I", d[:48])
    BPL, H, W, C = h[3], h[4], h[5], h[7]
    out = [collections.Counter() for _ in range(C)]
    ink = [0] * C
    for y in range(H):
        off = 48 + y * C * BPL
        for p in range(C):
            row = d[off + p*BPL: off + (p+1)*BPL]
            for x in range(W):
                byte = row[x >> 2] if (x >> 2) < len(row) else 0
                v = (byte >> (6 - 2*(x & 3))) & 3
                if v:
                    out[p][v] += 1
                    ink[p] += 1
    return ink, out
A = open(r"D:\work\RIP核心分析\work\shared\hssf_black64.prn", "rb").read()
B = open(r"D:\work\RIP核心分析\reference\prn_samples\probe_black_64_h13_m0.prn", "rb").read()
ia, ca = planes(A); ib, cb = planes(B)
names = ["K","C","M","Y","W1"]
for p in range(5):
    print("%s: ours ink=%6d hist=%s | oracle ink=%6d hist=%s" % (
        names[p], ia[p], dict(ca[p]), ib[p], dict(cb[p])))
