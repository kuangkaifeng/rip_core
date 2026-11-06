# -*- coding: utf-8 -*-
"""从 oracle 的 RGB 9^3 立方体探针 PRN 反解 RGB->设备墨值 3D LUT。

输入：
  work/shared/cube_planes/content_<i>_<code>.w3240h3240.bin   (mtr_prncheck content 导出)
  3rdparty/screen/thr_{C,M,Y,K}.bin                            (1024 加网 tile)
  reference/inputs/probe_rgbcube9_meta.json                    (色块布局)
输出：
  reference/profiles/rgb_cube9.bin
    magic "RGB9" + u16 size(=9) + u8 channels(=4) + 4 * 9^3 字节
    索引顺序: r-major, g, b-minor；rgb 级别 [0,32,64,96,128,160,192,224,255]
    每 ink 顺序: C,M,Y,K
  reference/profiles/rgb_cube9.json  (校验信息)
"""
import json, os, struct
from array import array

WS = r"D:\work\RIP核心分析"
PLANES = os.path.join(WS, "work", "shared", "cube_planes")
PROF = os.path.join(WS, "reference", "profiles")
SCREEN = os.path.join(WS, "3rdparty", "screen")
META = os.path.join(WS, "reference", "inputs", "probe_rgbcube9_meta.json")
os.makedirs(PROF, exist_ok=True)

meta = json.load(open(META, encoding="utf-8"))
levels = meta["levels"]; PITCH = meta["pitch"]; PATCH = meta["patch"]; N = len(levels)
order = meta["order"]  # [(r,g,b), ...] 729
assert len(order) == N ** 3 == 729

# ---- tile 阈值直方图 -> mean_pred(ink, v) ----
INKS = ["C", "M", "Y", "K"]
HIST = {}
for ink in INKS:
    d = open(os.path.join(SCREEN, "thr_%s.bin" % ink), "rb").read()
    assert len(d) == 1024 * 1024 * 3
    hs = []
    for k in range(3):
        h = [0] * 256
        for a in d[k::3]:
            h[a] += 1
        hs.append(h)
    cum = []
    for h in hs:
        c = [0] * 256
        s = 0
        for v in range(256):
            s += h[v]
            c[v] = s
        cum.append(c)
    # mean_pred[v] = (cum1[v]+cum2[v]+cum3[v]) / 1024^2
    mean = [(cum[0][v] + cum[1][v] + cum[2][v]) / (1024.0 * 1024.0) for v in range(256)]
    HIST[ink] = mean


def best_v(ink, target_mean):
    mean = HIST[ink]
    lo, hi = 0, 255
    while lo < hi:
        mid = (lo + hi) // 2
        if mean[mid] < target_mean:
            lo = mid + 1
        else:
            hi = mid
    best = lo
    bestd = abs(mean[best] - target_mean)
    for v in (lo - 1, lo + 1):
        if 0 <= v <= 255 and abs(mean[v] - target_mean) < bestd:
            best, bestd = v, abs(mean[v] - target_mean)
    return best


# ---- 读内容平面（content color code -> ink）----
CODE_TO_INK = {0x04: "K", 0x00: "C", 0x12: "M", 0x11: "Y"}
planes = {}
for fn in os.listdir(PLANES):
    if not fn.startswith("content_") or not fn.endswith(".bin"):
        continue
    code = int(fn.split("_")[-1][:2], 16)
    ink = CODE_TO_INK[code]
    data = open(os.path.join(PLANES, fn), "rb").read()
    assert len(data) == 3240 * 3240, (fn, len(data))
    planes[ink] = data
assert set(planes) == set(INKS), sorted(planes)

# ---- 每色块采样中心 60x60 ----
SCALE = 6          # content = image * 720/120
SAMPLE = 60
vals = {ink: [0] * 729 for ink in INKS}
report = {ink: {"max_err": 0, "errs": 0} for ink in INKS}
for idx, (r, g, b) in enumerate(order):
    col = idx % 27
    row = idx // 27
    # patch 图像坐标: x0 = col*PITCH+1, 中心 + PATCH/2
    cx = (col * PITCH + 1 + PATCH // 2) * SCALE
    cy = (row * PITCH + 1 + PATCH // 2) * SCALE
    x0 = cx - SAMPLE // 2
    y0 = cy - SAMPLE // 2
    for ink in INKS:
        data = planes[ink]
        total = 0
        for y in range(y0, y0 + SAMPLE):
            base = y * 3240 + x0
            for x in range(base, base + SAMPLE):
                total += data[x]
        mean = total / float(SAMPLE * SAMPLE)
        v = best_v(ink, mean)
        vals[ink][idx] = v
        pred = HIST[ink][v]
        err = abs(pred - mean)
        if err > report[ink]["max_err"]:
            report[ink]["max_err"] = err
        if err > 0.01:
            report[ink]["errs"] += 1

# ---- 写 bin ----
data = bytearray()
data += b"RGB9"
data += struct.pack("<H", N)
data += bytes([4])
for ink in INKS:
    data += bytes(vals[ink])
out = os.path.join(PROF, "rgb_cube9.bin")
open(out, "wb").write(bytes(data))
json.dump({"levels": levels, "order": order, "inks": INKS,
           "values": vals, "report": report}, open(os.path.join(PROF, "rgb_cube9.json"), "w"),
          indent=1)
print("wrote", out, len(data), "bytes")
for ink in INKS:
    print("%s: max mean-err=%.4f (level units), patches>0.01: %d/729" %
          (ink, report[ink]["max_err"], report[ink]["errs"]))
# 抽样打印：黑/白/红/绿/蓝/灰
lookup = {tuple(c): i for i, c in enumerate(order)}
for rgb in [(0,0,0), (255,255,255), (255,0,0), (0,255,0), (0,0,255), (128,128,128), (192,0,23), (0,0,128)]:
    i = lookup[rgb]
    print("RGB%-16s -> C%3d M%3d Y%3d K%3d" % (str(rgb), vals["C"][i], vals["M"][i], vals["Y"][i], vals["K"][i]))
