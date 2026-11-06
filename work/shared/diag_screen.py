# -*- coding: utf-8 -*-
import os, struct, hashlib, collections
WS = r"D:\work\RIP核心分析"
# 1) hash compare build/screen vs reference/screen
for f in ["thr_C.bin", "thr_M.bin", "thr_Y.bin", "thr_K.bin", "screen_meta.json"]:
    a = os.path.join(WS, "build", "screen", f)
    b = os.path.join(WS, "reference", "screen", f)
    ha = hashlib.sha256(open(a, "rb").read()).hexdigest()[:16] if os.path.exists(a) else "MISSING"
    hb = hashlib.sha256(open(b, "rb").read()).hexdigest()[:16] if os.path.exists(b) else "MISSING"
    print(f, "build=", ha, "ref=", hb, "SAME" if ha == hb and ha != "MISSING" else "DIFF")
# 2) 用 T3 阈值场 + oracle 墨值预测，对比 oracle 页面点阵
names = {0x00: "C", 0x12: "M", 0x11: "Y", 0x04: "K"}
thr = {}
for c, nm in names.items():
    d = open(os.path.join(WS, "build", "screen", "thr_%s.bin" % nm), "rb").read()
    thr[c] = d
# decode oracle gray000 page
import importlib.util
spec = importlib.util.spec_from_file_location("ve", os.path.join(WS, "tools", "validate", "validate_e2e.py"))
ve = importlib.util.module_from_spec(spec); spec.loader.exec_module(ve)
canvas = ve.decode_page(os.path.join(WS, "reference", "prn_samples", "probe_scan_gray000_a3dtf1390_m2.prn"))
target_v = {0x00: 189, 0x12: 174, 0x11: 170, 0x04: 174}
for c, nm in names.items():
    img = canvas[c]
    d = thr[c]
    for v in (target_v[c]-1, target_v[c], target_v[c]+1):
        eq = 0; tot = 0
        for y in range(384):
            row = img[y]
            for x in range(384):
                i = (y*384 + x)*3
                t1, t2, t3 = d[i], d[i+1], d[i+2]
                pred = (1 if v >= t1 else 0) + (1 if v >= t2 else 0) + (1 if v >= t3 else 0)
                if pred > 3: pred = 3
                if pred == row[x]: eq += 1
                tot += 1
        print("%s v=%d predict-match vs oracle = %.4f" % (nm, v, eq/tot))
