# -*- coding: utf-8 -*-
import os, importlib.util
WS = r"D:\work\RIP核心分析"
TILE = os.path.join(WS, "reference", "screen", "engine")
spec = importlib.util.spec_from_file_location("ve", os.path.join(WS, "tools", "validate", "validate_e2e.py"))
ve = importlib.util.module_from_spec(spec); spec.loader.exec_module(ve)

def load_tile(ink):
    return open(os.path.join(TILE, "thr_%s.bin" % ink), "rb").read()

def test(ink, top, tone, v):
    path = os.path.join(WS, "reference", "prn_samples", "probe_scan_%s%03d_a3dtf1390_m2.prn" % (ink, tone))
    if not os.path.exists(path):
        print("missing", path); return
    colors = {"C": 0x00, "Y": 0x11, "M": 0x12, "K": 0x04}
    c = colors[ink]
    canvas = ve.decode_page(path, offsets={c: top, 0x04: 640, 0x00: 640, 0x12: 644, 0x11: 644})
    img = canvas.get(c)
    if img is None:
        print(ink, tone, "no plane"); return
    d = load_tile(ink)
    size = 1024
    eq = 0; tot = 0
    for y in range(384):
        row = img[y]
        for x in range(384):
            i = ((y % size) * size + (x % size)) * 3
            t1, t2, t3 = d[i], d[i+1], d[i+2]
            p = (v >= t1) + (v >= t2) + (v >= t3)
            if p > 3: p = 3
            if p == row[x]: eq += 1
            tot += 1
    print("%s tone=%3d v=%3d match=%.5f" % (ink, tone, v, eq/tot))

for tone in (0, 16, 64, 128, 192, 240, 255):
    test("C", 640, tone, tone)
    test("Y", 644, tone, tone)
