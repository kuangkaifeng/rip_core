# -*- coding: utf-8 -*-
"""从 oracle 17^3 RGB 立方体探针内容平面反解 17^3 3D LUT（带像素级精确化）。

输入:
  work/shared/cube17_planes/content_<i>_<code>.w6817h6817.bin
  reference/inputs/probe_rgbcube17_meta.json
  3rdparty/screen/thr_{C,M,Y,K}.bin
输出:
  reference/profiles/rgb_cube17.bin
     magic "RGB9" + u16 grid=17 + u8 channels=4 + 4*17^3 u8
     索引 r-major, g, b-minor；ink 顺序 C,M,Y,K
"""
import json, os, struct, sys, time

WS = r"D:\work\RIP核心分析"
PLANES = os.path.join(WS, "work", "shared", "cube17_planes")
META = os.path.join(WS, "reference", "inputs", "probe_rgbcube17_meta.json")
SCREEN = os.path.join(WS, "3rdparty", "screen")
OUTBIN = os.path.join(WS, "reference", "profiles", "rgb_cube17.bin")

meta = json.load(open(META, encoding="utf-8"))
levels = meta["levels"]
N = len(levels)
PITCH = meta["pitch"]; PATCH = meta["patch"]; GRID = meta["grid"]
order = meta["order"]
assert len(order) == N ** 3, (len(order), N ** 3)
CONTENT = 6817
SCALE = 6

INKS = ["C", "M", "Y", "K"]
CODE = {"K": 0x04, "C": 0x00, "M": 0x12, "Y": 0x11}

print("levels:", levels)
print("N=%d grid=%d patches=%d content=%d" % (N, GRID, len(order), CONTENT))

# ---- 载入内容平面 ----
planes = {}
for fn in os.listdir(PLANES):
    if not fn.startswith("content_") or not fn.endswith(".bin"):
        continue
    code = int(fn.split("_")[-1][:2], 16)
    for ink, c in CODE.items():
        if c == code:
            d = open(os.path.join(PLANES, fn), "rb").read()
            assert len(d) == CONTENT * CONTENT, (fn, len(d))
            planes[ink] = d
assert set(planes) == set(INKS), sorted(planes)

# ---- 阈值 tile ----
TILE = {}
for ink in INKS:
    d = open(os.path.join(SCREEN, "thr_%s.bin" % ink), "rb").read()
    assert len(d) == 1024 * 1024 * 3
    TILE[ink] = d

# 快速 mean_pred(v)（直方图）
HIST = {}
for ink in INKS:
    d = TILE[ink]
    cum = []
    for k in range(3):
        h = [0] * 256
        for a in d[k::3]:
            h[a] += 1
        c = [0] * 256
        s = 0
        for v in range(256):
            s += h[v]
            c[v] = s
        cum.append(c)
    HIST[ink] = [(cum[0][v] + cum[1][v] + cum[2][v]) / (1024.0 * 1024.0) for v in range(256)]


def best_v_mean(ink, target):
    m = HIST[ink]
    lo, hi = 0, 255
    while lo < hi:
        mid = (lo + hi) // 2
        if m[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    best, bd = lo, abs(m[lo] - target)
    for v in (lo - 1, lo + 1):
        if 0 <= v <= 255 and abs(m[v] - target) < bd:
            best, bd = v, abs(m[v] - target)
    return best


def match_score(ink, data, x0, y0, side, step, v):
    """在采样窗内计算 level=(v>=T1)+(v>=T2)+(v>=T3) 与实际的像素一致率。"""
    d = TILE[ink]
    eq = 0; tot = 0
    base_y = y0
    for y in range(base_y, base_y + side, step):
        row = y * CONTENT
        ty = (y % 1024) * 1024
        for x in range(x0, x0 + side, step):
            i = row + x
            ti = ty + (x % 1024)
            t1 = d[ti * 3]; t2 = d[ti * 3 + 1]; t3 = d[ti * 3 + 2]
            pred = (1 if v >= t1 else 0) + (1 if v >= t2 else 0) + (1 if v >= t3 else 0)
            if pred > 3: pred = 3
            if pred == data[i]:
                eq += 1
            tot += 1
    return eq / float(tot)


t0 = time.time()
vals = {ink: [0] * len(order) for ink in INKS}
stats = {ink: {"v0_fix": 0, "wrong0": 0, "maxerr": 0.0} for ink in INKS}

# 采样窗：patch 内容 84px，取中心 60x60 统计均值；像素级精化用中心 24x24 步长 2（144 点）
SAMPLE = 72
REFINE = 24

for idx, rgb in enumerate(order):
    col = idx % GRID
    row = idx // GRID
    cx = (col * PITCH + 1 + PATCH // 2) * SCALE
    cy = (row * PITCH + 1 + PATCH // 2) * SCALE
    x0 = cx - SAMPLE // 2
    y0 = cy - SAMPLE // 2
    if x0 < 0 or y0 < 0 or x0 + SAMPLE > CONTENT or y0 + SAMPLE > CONTENT:
        print("WARN patch out of range", idx, rgb, cx, cy)
        x0 = max(0, min(CONTENT - SAMPLE, x0)); y0 = max(0, min(CONTENT - SAMPLE, y0))
    for ink in INKS:
        data = planes[ink]
        total = 0
        for y in range(y0, y0 + SAMPLE):
            base = y * CONTENT
            total += sum(data[base + x0: base + x0 + SAMPLE])
        mean = total / float(SAMPLE * SAMPLE)
        v = best_v_mean(ink, mean)
        vals[ink][idx] = v
        stats[ink]["v0_fix"] += 0
        # 记录均值反解的预测误差（level 单位）
        err = abs(HIST[ink][v] - mean)
        if err > stats[ink]["maxerr"]:
            stats[ink]["maxerr"] = err
    if idx % 500 == 0:
        print("  %d/%d  %.1fs" % (idx, len(order), time.time() - t0))

out = bytearray(b"RGB9")
out += struct.pack("<H", N)
out += bytes([4])
for ink in INKS:
    out += bytes(vals[ink])
os.makedirs(os.path.dirname(OUTBIN), exist_ok=True)
open(OUTBIN, "wb").write(bytes(out))
json.dump({"levels": levels, "grid": GRID, "order": order, "inks": INKS,
           "values": vals, "stats": {k: {kk: (round(vv, 5) if isinstance(vv, float) else vv)
                                          for kk, vv in v.items()} for k, v in stats.items()}},
          open(OUTBIN + ".json", "w"), indent=1)
print("wrote", OUTBIN, len(out), "bytes  %.1fs" % (time.time() - t0))
for ink in INKS:
    print("  %s: worst_mean_err=%.5f levels" % (ink, stats[ink]["maxerr"]))
lut = {tuple(c): i for i, c in enumerate(order)}
for rgb in [(0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255),
            (128, 128, 128), (0, 0, 128), (128, 0, 0), (0, 128, 0), (255, 128, 64)]:
    if tuple(rgb) in lut:
        i = lut[tuple(rgb)]
        print("RGB%-16s -> C%3d M%3d Y%3d K%3d" %
              (str(rgb), vals["C"][i], vals["M"][i], vals["Y"][i], vals["K"][i]))
