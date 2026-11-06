# -*- coding: utf-8 -*-
import os, importlib.util
WS = r"D:\work\RIP核心分析"
TILE = os.path.join(WS, "reference", "screen", "engine1024")
spec = importlib.util.spec_from_file_location("ve", os.path.join(WS, "tools", "validate", "validate_e2e.py"))
ve = importlib.util.module_from_spec(spec); spec.loader.exec_module(ve)
TILES = {}
for nm in ["C", "M", "Y", "K"]:
    TILES[nm] = open(os.path.join(TILE, "thr_%s.bin" % nm), "rb").read()
CODE = {"C": 0x00, "M": 0x12, "Y": 0x11, "K": 0x04}
TOP = {0x00: 640, 0x04: 640, 0x12: 644, 0x11: 644}
for ink in ["C", "M", "Y", "K"]:
    d = TILES[ink]
    c = CODE[ink]
    for tone in (16, 64, 128, 192, 240, 255):
        p = os.path.join(WS, "reference", "prn_samples", "probe_scan_%s%03d_a3dtf1390_m2.prn" % (ink, tone))
        if not os.path.exists(p):
            print("missing", p); continue
        canvas = ve.decode_page(p, offsets={c: TOP[c], 0x04: 640, 0x00: 640, 0x12: 644, 0x11: 644})
        img = canvas.get(c)
        if img is None:
            continue
        v = tone
        eq = tot = 0
        size = 1024
        for y in range(384):
            row = img[y]
            for x in range(384):
                i = ((y % size) * size + (x % size)) * 3
                t1, t2, t3 = d[i], d[i+1], d[i+2]
                pr = (1 if v >= t1 else 0) + (1 if v >= t2 else 0) + (1 if v >= t3 else 0)
                if pr > 3: pr = 3
                if pr == row[x]: eq += 1
                tot += 1
        print("%s tone=%3d match=%.5f" % (ink, tone, eq/tot))
