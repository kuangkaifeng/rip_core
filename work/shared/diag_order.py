# -*- coding: utf-8 -*-
import os, importlib.util
WS = r"D:\work\RIP核心分析"
names = {0x00: "C", 0x12: "M", 0x11: "Y", 0x04: "K"}
thr = {}
for c, nm in names.items():
    thr[c] = open(os.path.join(WS, "build", "screen", "thr_%s.bin" % nm), "rb").read()
spec = importlib.util.spec_from_file_location("ve", os.path.join(WS, "tools", "validate", "validate_e2e.py"))
ve = importlib.util.module_from_spec(spec); spec.loader.exec_module(ve)
canvas = ve.decode_page(os.path.join(WS, "reference", "prn_samples", "probe_scan_gray000_a3dtf1390_m2.prn"))
base_v = {0x00: 189, 0x12: 174, 0x11: 170, 0x04: 174}

def predict_match(c, remap, v):
    img = canvas[c]; d = thr[c]
    eq = 0; tot = 0
    for y in range(384):
        row = img[y]
        for x in range(384):
            xs = (x & ~3) + (3 - (x & 3)) if remap else x
            i = (y*384 + xs)*3
            t1, t2, t3 = d[i], d[i+1], d[i+2]
            p = (v >= t1) + (v >= t2) + (v >= t3)
            if p > 3: p = 3
            if p == row[x]: eq += 1
            tot += 1
    return eq/tot

for c, nm in names.items():
    best = None
    for remap in (False, True):
        for dv in (-2,-1,0,1,2):
            v = base_v[c] + dv
            m = predict_match(c, remap, v)
            if best is None or m > best[0]:
                best = (m, remap, v)
    print("%s: best match=%.4f remap=%s v=%d" % (nm, best[0], best[1], best[2]))
