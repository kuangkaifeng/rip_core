# -*- coding: utf-8 -*-
# 在 fit_gray_calib2.py 基础上：best_v 用像素级匹配精确化
p = r"D:\work\RIP核心分析\tools\color_tools\fit_gray_calib2.py"
t = open(p, encoding="utf-8").read()
old = """def best_v(ink, target_mean):
    lo, hi = 0, 255
    best = min(range(256), key=lambda v: abs(mean_pred(ink, v) - target_mean))
    return best"""
new = """def best_v(ink, target_mean):
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
    return best[1]"""
assert old in t
t = t.replace(old, new)
old2 = """        obs = sum(sum(row) for row in img) / (384.0 * 384.0)
        vo.append(best_v(nm, obs))"""
new2 = """        obs = sum(sum(row) for row in img) / (384.0 * 384.0)
        v0 = best_v(nm, obs)
        vo.append(best_v_pixel(nm, img, v0))"""
assert old2 in t
t = t.replace(old2, new2)
open(p, "w", encoding="utf-8", newline="").write(t)
print("fit script refined")
