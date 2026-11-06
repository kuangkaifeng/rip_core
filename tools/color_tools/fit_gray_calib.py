# -*- coding: utf-8 -*-
"""从 oracle 的 RGB 中性灰探针反推 RGB->CMYK 数值链，并生成 1D 标定 LUT。

方法：
  oracle: 对 gray(t) 的 PRN 解码页面点阵 -> 每通道平均 level -> v_oracle = mean*255/3
  ours  : 用 PIL ImageCms (lcms2) 按 sRGB->CoatedFOGRA39 perceptual 计算 gray(t) 的 CMYK
  拟合：对每通道建立 v_icc -> v_oracle 的 256 项 LUT（单调化+插值）
输出：build/color/calib_gray.bin （4*256 uint8，顺序 C,M,Y,K）+ 报告 JSON
"""
import os, sys, struct, json
from collections import defaultdict
from PIL import Image, ImageCms

WS = r"D:\work\RIP核心分析"
PR = os.path.join(WS, "reference", "prn_samples")
OUT = os.path.join(WS, "build", "color")
os.makedirs(OUT, exist_ok=True)

# ---- PRN 解码（ESC/P2 -> 每色页面点阵，已知内容 384x384，mode2）----
def decode_rle(buf, j, need):
    dec = bytearray(); n = len(buf)
    while j < n and len(dec) < need:
        c = buf[j]
        if c <= 127:
            cnt = c + 1; dec += buf[j+1:j+1+cnt]; j += 1 + cnt
        else:
            cnt = 257 - c
            if j + 1 >= n: break
            dec += bytes([buf[j+1]]) * cnt; j += 2
    return bytes(dec[:need]), j

def parse_page(path, content=384, offsets=None):
    """offsets: {color: content_top_page_row}"""
    if offsets is None:
        offsets = {0x04: 640, 0x00: 640, 0x12: 644, 0x11: 644}
    buf = open(path, "rb").read()
    q = buf.find(b"\x1b\x00\x00\x00")
    pos = q + 4 if q > 0 else 0
    # command region
    cmds = {}
    while pos + 2 <= len(buf):
        if buf[pos] != 0x1B: pos += 1; continue
        b1 = buf[pos+1]
        if b1 == 0x28:
            cmd = buf[pos+2]; ln = buf[pos+3] | (buf[pos+4] << 8)
            if cmd == 0x24: break
            cmds[cmd] = buf[pos+5:pos+5+ln]; pos += 5 + ln
        else: pos += 2
    U = cmds.get(0x55, b""); D = cmds.get(0x44, b"")
    pageunit = 2880 // U[0] if U else 720
    r = (D[0] | (D[1] << 8)) if len(D) >= 4 else 1440
    v = D[2] if len(D) >= 4 else 16
    vstep = pageunit // (r // v)
    blocks = []; cur = dict(adv=None, recs=[]); p2 = pos
    while True:
        i = buf.find(b"\x1b", p2)
        if i < 0 or i + 2 >= len(buf): break
        b1 = buf[i+1]
        if b1 == 0x69 and i + 9 <= len(buf):
            color = buf[i+2]; n = buf[i+5] | (buf[i+6] << 8); m = buf[i+7] | (buf[i+8] << 8)
            raw, j = decode_rle(buf, i+9, n*m)
            cur["recs"].append(dict(color=color, n=n, m=m, raw=raw)); p2 = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i+2]; ln = buf[i+3] | (buf[i+4] << 8)
            if cmd == 0x76 and ln >= 4:
                if cur["recs"]: blocks.append(cur)
                cur = dict(adv=struct.unpack("<I", buf[i+5:i+9])[0], recs=[])
            p2 = i + 5 + ln
        else: p2 = i + 1
    if cur["recs"]: blocks.append(cur)
    p = 0
    for b in blocks:
        if b["adv"] is not None: p += b["adv"]
        b["pos"] = p
    canvas = {}
    for b in blocks:
        for rec in b["recs"]:
            c = rec["color"]
            if c not in canvas:
                canvas[c] = [[0]*content for _ in range(content)]
            top = offsets.get(c, 640)
            for row in range(rec["m"]):
                prow = b["pos"] + vstep*row - top
                if not (0 <= prow < content): continue
                line = rec["raw"][row*rec["n"]:(row+1)*rec["n"]]
                for x in range(content):
                    byte = line[x >> 2] if (x >> 2) < len(line) else 0
                    val = (byte >> (6 - 2*(x & 3))) & 3
                    if val: canvas[c][prow][x] = val
    return canvas

def mean_level(canvas, content=384):
    out = {}
    for c, img in canvas.items():
        tot = sum(sum(row) for row in img)
        out[c] = tot / (content*content)
    return out

# ---- lcms2 via PIL ----
SRGB = os.path.join(WS, "reference", "profiles", "source", "RGB", "SRGB IEC61966-2.1.icc")
FOGRA = os.path.join(WS, "reference", "profiles", "source", "CMYK", "CoatedFOGRA39.icc")
if not os.path.exists(SRGB):
    SRGB = os.path.join(WS, "3rdparty", "icc", "SRGB IEC61966-2.1.icc")
if not os.path.exists(FOGRA):
    FOGRA = os.path.join(WS, "3rdparty", "icc", "CoatedFOGRA39.icc")
print("profiles:", SRGB, FOGRA)
src = ImageCms.getOpenProfile(SRGB)
dst = ImageCms.getOpenProfile(FOGRA)

def icc_cmyk(rgb):
    tf = ImageCms.buildTransform(src, dst, "RGB", "CMYK",
                                 renderingIntent=ImageCms.Intent.PERCEPTUAL, flags=0)
    im = Image.new("RGB", (1, 1), rgb)
    return ImageCms.applyTransform(im, tf).getpixel((0, 0))

CH = [0x00, 0x12, 0x11, 0x04]  # C,M,Y,K
NAMES = ["C", "M", "Y", "K"]
samples = []  # (t, v_oracle[4], v_icc[4])
for t in range(0, 256, 8):
    path = os.path.join(PR, "probe_scan_gray%03d_a3dtf1390_m2.prn" % t)
    if not os.path.exists(path):
        continue
    canvas = parse_page(path)
    means = mean_level(canvas)
    vo = [means.get(c) for c in CH]
    if any(v is None for v in vo):
        continue
    vo = [x * 255.0 / 3.0 for x in vo]
    vi = list(icc_cmyk((t, t, t)))
    samples.append((t, vo, vi))
print("samples:", len(samples))
for s in samples[:5]:
    print("  t=%3d oracle=%s icc=%s" % (s[0], ["%.1f" % x for x in s[1]], s[2]))

# ---- 拟合每通道 LUT：v_icc -> v_oracle ----
lut = [[0]*256 for _ in range(4)]
report = {}
for ch in range(4):
    xs = [s[2][ch] for s in samples]
    ys = [s[1][ch] for s in samples]
    # 白色锚点：纯白输入 -> 墨量 0（oracle 对 flat_white 输出无栅格）
    xs.append(0); ys.append(0.0)
    pairs = sorted(zip(xs, ys))
    # 去重取平均
    agg = defaultdict(list)
    for x, y in pairs:
        agg[x].append(y)
    px = sorted(agg.keys())
    py = [sum(agg[x])/len(agg[x]) for x in px]
    # 单调化（保序回归的简单近似：累积最大）
    for i in range(1, len(py)):
        if py[i] < py[i-1]: py[i] = py[i-1]
    # 线性插值 + 端点外推
    def f(v):
        if not px: return v
        if v <= px[0]: return py[0]
        if v >= px[-1]: return py[-1]
        import bisect
        i = bisect.bisect_right(px, v) - 1
        if i >= len(px)-1: return py[-1]
        x0, x1 = px[i], px[i+1]
        y0, y1 = py[i], py[i+1]
        if x1 == x0: return y1
        return y0 + (y1-y0)*(v-x0)/(x1-x0)
    for v in range(256):
        lut[ch][v] = max(0, min(255, int(round(f(v)))))
    lut[ch][0] = 0
    # 保证单调
    for v in range(1, 256):
        if lut[ch][v] < lut[ch][v-1]:
            lut[ch][v] = lut[ch][v-1]
    report[NAMES[ch]] = {"pairs": len(px),
                         "icc_black": px[0] if px else None,
                         "oracle_black": round(py[0],1) if py else None,
                         "icc_white": px[-1] if px else None,
                         "oracle_white": round(py[-1],1) if py else None}

data = bytearray()
for ch in range(4):
    data += bytes(lut[ch])
open(os.path.join(OUT, "calib_gray.bin"), "wb").write(bytes(data))
json.dump({"samples": [[s[0], [round(x,2) for x in s[1]], list(s[2])] for s in samples],
           "report": report}, open(os.path.join(OUT, "calib_gray.json"), "w", encoding="utf-8"),
          indent=1)
print("calib written:", os.path.join(OUT, "calib_gray.bin"), len(data))
print(json.dumps(report, indent=1))
