# -*- coding: utf-8 -*-
"""通用：从 oracle RGB 立方体探针 PRN 的内容平面反解 N^3 3D LUT。

用法:
  python build_rgb_cube_lut.py <planes_dir> <meta_json> <content_size> <out_bin> [--mode-name]
示例:
  python build_rgb_cube_lut.py work/shared/cube17_planes reference/inputs/probe_rgbcube17_meta.json 6816 reference/profiles/rgb_cube17.bin

平面文件名约定（mtr_prncheck content 输出）：content_<i>_<code>.w<W>h<H>.bin
  code -> ink: 04=K, 00=C, 12=M, 11=Y
输出 bin:
  magic "RGB9" + u16 grid + u8 channels(4) + 4*grid^3 u8
  （magic 固定为 RGB9 以兼容引擎加载器；grid 字段表示实际网格 N）
索引顺序: r-major, g, b-minor（与 meta["order"] 一致）
"""
import json, os, struct, sys
from array import array

WS = r"D:\work\RIP核心分析"
SCREEN = os.path.join(WS, "3rdparty", "screen")
INKS = ["C", "M", "Y", "K"]
CODE_TO_INK = {0x04: "K", 0x00: "C", 0x12: "M", 0x11: "Y"}


def build_hist():
    hist = {}
    for ink in INKS:
        d = open(os.path.join(SCREEN, "thr_%s.bin" % ink), "rb").read()
        assert len(d) == 1024 * 1024 * 3
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
        hist[ink] = [(cum[0][v] + cum[1][v] + cum[2][v]) / (1024.0 * 1024.0) for v in range(256)]
    return hist


def best_v(mean, target):
    lo, hi = 0, len(mean) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if mean[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    best, bd = lo, abs(mean[lo] - target)
    for v in (lo - 1, lo + 1):
        if 0 <= v < len(mean) and abs(mean[v] - target) < bd:
            best, bd = v, abs(mean[v] - target)
    return best


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    planes_dir, meta_path, content_size, out_bin = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    meta = json.load(open(meta_path, encoding="utf-8"))
    levels = meta["levels"]
    N = len(levels)
    PITCH = meta["pitch"]
    PATCH = meta["patch"]
    order = meta["order"]
    assert len(order) == N ** 3, (len(order), N ** 3)
    grid = int(round(N ** 0.5 * 0 + 0)) or int(round(len(order) ** (1 / 3.0)))
    rows = meta.get("grid", grid)
    print("N=%d grid=%d patches=%d content=%d" % (N, rows, len(order), content_size))

    planes = {}
    for fn in os.listdir(planes_dir):
        if not fn.startswith("content_") or not fn.endswith(".bin"):
            continue
        code = int(fn.split("_")[-1][:2], 16)
        ink = CODE_TO_INK.get(code)
        if not ink:
            continue
        d = open(os.path.join(planes_dir, fn), "rb").read()
        assert len(d) == content_size * content_size, (fn, len(d), content_size)
        planes[ink] = d
    assert set(planes) == set(INKS), sorted(planes)

    SCALE = 720 // 120  # 120dpi 输入 -> 720dpi 内容 = 6x（探针约定 120dpi）
    hist = build_hist()
    vals = {ink: [0] * len(order) for ink in INKS}
    errs = {ink: 0.0 for ink in INKS}
    worst = {ink: 0.0 for ink in INKS}

    for idx, rgb in enumerate(order):
        col = idx % rows
        row = idx // rows
        cx = (col * PITCH + 1 + PATCH // 2) * SCALE
        cy = (row * PITCH + 1 + PATCH // 2) * SCALE
        half = max(2, (PATCH * SCALE) // 3) // 2
        x0 = max(0, min(content_size - 2 * half, cx - half))
        y0 = max(0, min(content_size - 2 * half, cy - half))
        w = h = 2 * half
        npx = w * h
        for ink in INKS:
            data = planes[ink]
            total = 0
            for y in range(y0, y0 + h):
                base = y * content_size + x0
                for x in range(base, base + w):
                    total += data[x]
            mean = total / float(npx)
            v = best_v(hist[ink], mean)
            vals[ink][idx] = v
            err = abs(hist[ink][v] - mean)
            errs[ink] += err
            if err > worst[ink]:
                worst[ink] = err

    out = bytearray(b"RGB9")
    out += struct.pack("<H", N)
    out += bytes([4])
    for ink in INKS:
        out += bytes(vals[ink])
    os.makedirs(os.path.dirname(out_bin), exist_ok=True)
    open(out_bin, "wb").write(bytes(out))
    stats = {ink: {"mean_err_levels": round(errs[ink] / len(order), 5),
                   "worst_err_levels": round(worst[ink], 5)} for ink in INKS}
    json.dump({"levels": levels, "order": order, "inks": INKS, "values": vals, "stats": stats},
              open(out_bin + ".json", "w"), indent=1)
    print("wrote", out_bin, len(out), "bytes")
    for ink in INKS:
        print("  %s: mean_err=%.5f worst_err=%.5f (level units)" %
              (ink, stats[ink]["mean_err_levels"], stats[ink]["worst_err_levels"]))
    lut = {tuple(c): i for i, c in enumerate(order)}
    for rgb in [(0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255),
                (128, 128, 128), (0, 0, 128), (128, 0, 0), (0, 128, 0)]:
        if tuple(rgb) in lut:
            i = lut[tuple(rgb)]
            print("RGB%-16s -> C%3d M%3d Y%3d K%3d" %
                  (str(rgb), vals["C"][i], vals["M"][i], vals["Y"][i], vals["K"][i]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
