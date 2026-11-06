# -*- coding: utf-8 -*-
"""灰度轴精确标定（v2）：
利用 1024×1024 精确阈值 tile + oracle 灰度探针 PRN：
  1) 对每个 gray(t) 的 oracle 页面点阵，求该通道**整数墨值 v***：
     v* = argmin_v | mean_pred(v) - mean_obs |，mean_pred 用 tile 阈值精确计算。
  2) 用 PIL lcms2 计算我们 ICC 对同一 gray(t) 的输出 v_icc。
  3) 拟合 v_icc -> v* 的 256 项 LUT（含 (0,0) 锚点、单调、LUT[0]=0）。
输出: build/color/calib_gray.bin（4*256 uint8，顺序 C,M,Y,K）
"""
import os, sys, struct, json, bisect
from collections import defaultdict
from PIL import Image, ImageCms

WS = r"D:\work\RIP核心分析"
PR = os.path.join(WS, "reference", "prn_samples")
SCREEN = os.path.join(WS, "build", "screen")
OUT = os.path.join(WS, "build", "color")
os.makedirs(OUT, exist_ok=True)

# ---- 解码 oracle 页面点阵（MSB 解包；内容 384x384；C/K top=640, M/Y=644）----
def decode_page(path, content=384):
    offsets = {0x04: 640, 0x00: 640, 0x12: 644, 0x11: 644}
    buf = open(path, "rb").read()
    q = buf.find(b"\x1b\x00\x00\x00")
    pos = q + 4 if q > 0 else 0
    cmds = {}
    while pos + 2 <= len(buf):
        if buf[pos] != 0x1B:
            pos += 1
            continue
        b1 = buf[pos + 1]
        if b1 == 0x28:
            cmd = buf[pos + 2]
            ln = buf[pos + 3] | (buf[pos + 4] << 8)
            if cmd == 0x24:
                break
            cmds[cmd] = buf[pos + 5:pos + 5 + ln]
            pos += 5 + ln
        else:
            pos += 2
    U = cmds.get(0x55, b"")
    D = cmds.get(0x44, b"")
    pageunit = 2880 // U[0] if U else 720
    rr = (D[0] | (D[1] << 8)) if len(D) >= 4 else 1440
    vv = D[2] if len(D) >= 4 else 16
    vstep = pageunit // (rr // vv)

    def rle(j, need):
        dec = bytearray()
        n = len(buf)
        while j < n and len(dec) < need:
            c = buf[j]
            if c <= 127:
                cnt = c + 1
                dec += buf[j + 1:j + 1 + cnt]
                j += 1 + cnt
            else:
                cnt = 257 - c
                if j + 1 >= n:
                    break
                dec += bytes([buf[j + 1]]) * cnt
                j += 2
        return bytes(dec[:need]), j

    blocks = []
    cur = {"adv": None, "recs": []}
    p2 = pos
    while True:
        i = buf.find(b"\x1b", p2)
        if i < 0 or i + 2 >= len(buf):
            break
        b1 = buf[i + 1]
        if b1 == 0x69 and i + 9 <= len(buf):
            color = buf[i + 2]
            n = buf[i + 5] | (buf[i + 6] << 8)
            m = buf[i + 7] | (buf[i + 8] << 8)
            raw, j = rle(i + 9, n * m)
            cur["recs"].append({"color": color, "n": n, "m": m, "raw": raw})
            p2 = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i + 2]
            ln = buf[i + 3] | (buf[i + 4] << 8)
            if cmd == 0x76 and ln >= 4:
                if cur["recs"]:
                    blocks.append(cur)
                cur = {"adv": struct.unpack("<I", buf[i + 5:i + 9])[0], "recs": []}
            p2 = i + 5 + ln
        else:
            p2 = i + 1
    if cur["recs"]:
        blocks.append(cur)
    p = 0
    for b in blocks:
        if b["adv"] is not None:
            p += b["adv"]
        b["pos"] = p
    canvas = {}
    for b in blocks:
        for rec in b["recs"]:
            c = rec["color"]
            if c not in canvas:
                canvas[c] = [[0] * content for _ in range(content)]
            top = offsets.get(c, 640)
            for row in range(rec["m"]):
                prow = b["pos"] + vstep * row - top
                if not (0 <= prow < content):
                    continue
                line = rec["raw"][row * rec["n"]:(row + 1) * rec["n"]]
                for x in range(content):
                    byte = line[x >> 2] if (x >> 2) < len(line) else 0
                    val = (byte >> (6 - 2 * (x & 3))) & 3
                    if val:
                        canvas[c][prow][x] = val
    return canvas


# ---- 载入 1024 tile ----
def load_tile(ink):
    d = open(os.path.join(SCREEN, "thr_%s.bin" % ink), "rb").read()
    assert len(d) == 1024 * 1024 * 3, (ink, len(d))
    return d


TILES = {nm: load_tile(nm) for nm in ["C", "M", "Y", "K"]}
INK = {0x00: "C", 0x12: "M", 0x11: "Y", 0x04: "K"}

# 预计算：tile 的 T1/T2/T3 频率直方图（用于 mean_pred(v) 快速精确计算）
# mean_pred(v) = (#T1<=v + #T2<=v + #T3<=v)/Npix（只取页面像素区域，tile 全域均有效）
HISTS = {}
for nm, d in TILES.items():
    t1 = d[0::3]
    t2 = d[1::3]
    t3 = d[2::3]
    def hist(arr):
        h = [0] * 256
        for a in arr:
            h[a] += 1
        return h
    HISTS[nm] = [hist(t1), hist(t2), hist(t3)]


def mean_pred(ink, v):
    n = 1024 * 1024
    total = 0
    for h in HISTS[ink]:
        total += sum(h[:v + 1])
    return total / n


def best_v(ink, target_mean):
    return min(range(256), key=lambda v: abs(mean_pred(ink, v) - target_mean))


def pixel_match(ink, canvas_img, v, content=384):
    d = TILES[ink]
    eq = tot = 0
    for y in range(content):
        row = canvas_img[y]
        for x in range(content):
            i = ((y % 1024) * 1024 + (x % 1024)) * 3
            t1, t2, t3 = d[i], d[i + 1], d[i + 2]
            pred = (v >= t1) + (v >= t2) + (v >= t3)
            if pred > 3:
                pred = 3
            if pred == row[x]:
                eq += 1
            tot += 1
    return eq / tot


def best_v_pixel(ink, canvas_img, v0):
    best = (pixel_match(ink, canvas_img, v0), v0)
    for dv in (-2, -1, 1, 2):
        v = max(0, min(255, v0 + dv))
        m = pixel_match(ink, canvas_img, v)
        if m > best[0]:
            best = (m, v)
    return best[1]


# ---- 引擎自身 ICC 数值链（mtr_cli gray 输出，避免与 PIL/lcms 版本差异）----
import subprocess
CLI = os.path.join(WS, "build", "mtr_cli.exe")
PRS = os.path.join(WS, "reference", "prs", "A3-DTF-1390.prs").replace("\\", "/")
ENGINE_ICC = {}
r = subprocess.run([CLI, "gray", "--prs", PRS, "--mode", "2"],
                   capture_output=True, text=True, cwd=os.path.join(WS, "build"))
assert r.returncode == 0, r.stderr
for line in r.stdout.strip().splitlines():
    parts = [int(x) for x in line.split()]
    ENGINE_ICC[parts[0]] = parts[1:5]
print("engine gray ICC loaded:", len(ENGINE_ICC))


def icc_cmyk(t):
    return tuple(ENGINE_ICC[t])


CH_ORDER = ["C", "M", "Y", "K"]
samples = []
for t in range(0, 256, 8):
    path = os.path.join(PR, "probe_scan_gray%03d_a3dtf1390_m2.prn" % t)
    if not os.path.exists(path):
        continue
    canvas = decode_page(path)
    if not canvas:
        continue
    vo = []
    ok = True
    for nm in CH_ORDER:
        c = {"C": 0x00, "M": 0x12, "Y": 0x11, "K": 0x04}[nm]
        img = canvas.get(c)
        if img is None:
            ok = False
            break
        obs = sum(sum(row) for row in img) / (384.0 * 384.0)
        v0 = best_v(nm, obs)
        vo.append(best_v_pixel(nm, img, v0))
    if not ok:
        continue
    vi = list(icc_cmyk(t))
    samples.append((t, vo, vi))

print("samples:", len(samples))
for s in samples[:4]:
    print("  t=%3d oracle_v=%s icc=%s" % (s[0], s[1], s[2]))

# ---- 拟合 LUT：v_icc -> v* ----
lut = [[0] * 256 for _ in range(4)]
for ch, nm in enumerate(CH_ORDER):
    xs = [s[2][ch] for s in samples]
    ys = [s[1][ch] for s in samples]
    xs.append(0)
    ys.append(0)
    agg = defaultdict(list)
    for x, y in zip(xs, ys):
        agg[x].append(y)
    px = sorted(agg)
    py = [max(agg[x]) for x in px]  # 保序
    for i in range(1, len(py)):
        if py[i] < py[i - 1]:
            py[i] = py[i - 1]

    def f(v):
        if v <= px[0]:
            return py[0]
        if v >= px[-1]:
            return py[-1]
        i = bisect.bisect_right(px, v) - 1
        x0, x1 = px[i], px[i + 1]
        y0, y1 = py[i], py[i + 1]
        if x1 == x0:
            return y1
        return y0 + (y1 - y0) * (v - x0) / (x1 - x0)

    for v in range(256):
        lut[ch][v] = max(0, min(255, int(round(f(v)))))
    lut[ch][0] = 0
    for v in range(1, 256):
        if lut[ch][v] < lut[ch][v - 1]:
            lut[ch][v] = lut[ch][v - 1]
    print("  %s: pairs=%d  lut[64]=%d lut[128]=%d lut[192]=%d lut[255]=%d" % (
        nm, len(px), lut[ch][64], lut[ch][128], lut[ch][192], lut[ch][255]))

data = bytearray()
for ch in range(4):
    data += bytes(lut[ch])
open(os.path.join(OUT, "calib_gray_engine.bin"), "wb").write(bytes(data))
json.dump({"samples": [[s[0], s[1], s[2]] for s in samples],
           "lut": lut}, open(os.path.join(OUT, "calib_gray.json"), "w", encoding="utf-8"),
          indent=1)
print("calib v2 written:", os.path.join(OUT, "calib_gray_engine.bin"))
