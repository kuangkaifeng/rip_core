# -*- coding: utf-8 -*-
import collections, os
ws = r"D:\work\RIP核心分析"
# 1) threshold file stats
for name in ["thr_C.bin"]:
    d = open(os.path.join(ws, "build", "screen", name), "rb").read()
    print(name, "size", len(d))
    t1 = d[0::3]; t2 = d[1::3]; t3 = d[2::3]
    for nm, arr in (("T1", t1), ("T2", t2), ("T3", t3)):
        c = collections.Counter(arr)
        print(" ", nm, "min", min(arr), "max", max(arr), "mean %.1f" % (sum(arr)/len(arr)), "top", c.most_common(4))
# 2) grep engine-dev changes in escp2_writer.cpp
p = os.path.join(ws, "src", "core", "encode", "escp2_writer.cpp")
t = open(p, encoding="utf-8").read()
i = t.find("void Escp2Writer::addBlock")
print("\n=== addBlock ===\n", t[i:i+1800] if i >= 0 else "NOT FOUND")
