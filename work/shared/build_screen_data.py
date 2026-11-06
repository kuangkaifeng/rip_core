# -*- coding: utf-8 -*-
import struct, json, os
WS = r"D:\work\RIP核心分析"
BIN = os.path.join(WS, "work", "protocol", "evidence", "probe_scan_thresholds.bin")
OUT = os.path.join(WS, "build", "screen")
os.makedirs(OUT, exist_ok=True)
raw = open(BIN, "rb").read()
N = 449280
assert len(raw) >= 3 * N * 2, len(raw)
T = []
for c in range(3):
    arr = struct.unpack_from("<%dH" % N, raw, c * N * 2)
    T.append(arr)
print("loaded", len(raw), "bytes; N=", N)
# 64x64 probe, mode2, 13 blocks. 位置：block k pos=79k（首块 0），raster 行步 8，P0=640
# raster order: record(k) -> row r -> x(0..383)
size = 384
field = [[None] * (size * size) for _ in range(3)]
owner = [False] * (size * size)
pos = [79 * k for k in range(13)]
for k in range(13):
    for r in range(90):
        p = pos[k] + 8 * r
        if not (640 <= p <= 1023):
            continue
        prow = p - 640
        base = ((k * 90) + r) * 384
        for x in range(384):
            idx = base + x
            pidx = prow * 384 + x
            t1 = T[0][idx]
            if t1 == 0:
                continue
            if not owner[pidx]:
                for c in range(3):
                    field[c][pidx] = T[c][idx]
                owner[pidx] = True
owned = sum(owner)
print("page pixels owned:", owned, "of", size * size)
import collections
print("T1 histogram head:", collections.Counter(field[0][i] for i in range(size*size) if field[0][i]).most_common(6))
# 输出：每通道 3 字节/像素
names = ["C", "M", "Y", "K"]
meta = {"size": size, "channels": []}
for ci, name in enumerate(names):
    data = bytearray(size * size * 3)
    for i in range(size * size):
        t1 = field[0][i] if field[0][i] is not None else 1
        t2 = field[1][i] if field[1][i] is not None else 86
        t3 = field[2][i] if field[2][i] is not None else 171
        data[i*3+0] = min(t1, 255)
        data[i*3+1] = min(t2, 255)
        data[i*3+2] = min(t3, 255)
    fn = "thr_%s.bin" % name
    open(os.path.join(OUT, fn), "wb").write(bytes(data))
    meta["channels"].append({"ink": name, "file": fn, "approx": ci != 0, "phaseX": 0, "phaseY": 0})
json.dump(meta, open(os.path.join(OUT, "screen_meta.json"), "w", encoding="utf-8"), indent=1)
print("screen data written ->", OUT)
