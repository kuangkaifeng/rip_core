# -*- coding: utf-8 -*-
import struct
WS = r"D:\work\RIP核心分析"
def planes(d):
    h = struct.unpack("<12I", d[:48])
    BPL, H, W, C = h[3], h[4], h[5], h[7]
    out = []
    for p in range(C):
        out.append([[0]*W for _ in range(H)])
    for y in range(H):
        off = 48 + y * C * BPL
        for p in range(C):
            row = d[off + p*BPL: off + (p+1)*BPL]
            for x in range(W):
                byte = row[x >> 2] if (x >> 2) < len(row) else 0
                out[p][y][x] = (byte >> (6 - 2*(x & 3))) & 3
    return out
A = open(WS + r"\work\shared\hssf_black64.prn", "rb").read()
B = open(WS + r"\reference\prn_samples\probe_black_64_h13_m0.prn", "rb").read()
pa, pb = planes(A), planes(B)
names = ["K","C","M","Y","W1"]
for p in range(5):
    eq = tot = 0; ia = ib = 0
    for y in range(384):
        for x in range(384):
            va = pa[p][y][x]; vb = pb[p][y][x]
            if va: ia += 1
            if vb: ib += 1
            if va == vb: eq += 1
            tot += 1
    print("%s: match=%.4f ink ours=%6d oracle=%6d" % (names[p], eq/tot, ia, ib))
