# -*- coding: utf-8 -*-
# 1) fit script: add (0,0) anchor
p = r"D:\work\RIP核心分析\tools\color_tools\fit_gray_calib.py"
t = open(p, encoding="utf-8").read()
old = """    xs = [s[2][ch] for s in samples]
    ys = [s[1][ch] for s in samples]
    pairs = sorted(zip(xs, ys))"""
new = """    xs = [s[2][ch] for s in samples]
    ys = [s[1][ch] for s in samples]
    # 白色锚点：纯白输入 -> 墨量 0（oracle 对 flat_white 输出无栅格）
    xs.append(0); ys.append(0.0)
    pairs = sorted(zip(xs, ys))"""
assert old in t
t = t.replace(old, new)
# also force lut[0]=0
old2 = """    for v in range(256):
        lut[ch][v] = max(0, min(255, int(round(f(v)))))"""
new2 = """    for v in range(256):
        lut[ch][v] = max(0, min(255, int(round(f(v)))))
    lut[ch][0] = 0
    # 保证单调
    for v in range(1, 256):
        if lut[ch][v] < lut[ch][v-1]:
            lut[ch][v] = lut[ch][v-1]"""
assert old2 in t
t = t.replace(old2, new2)
open(p, "w", encoding="utf-8", newline="").write(t)
print("fit script patched")

# 2) validate script: print implied mean ink v
p2 = r"D:\work\RIP核心分析\tools\validate\validate_e2e.py"
t2 = open(p2, encoding="utf-8").read()
old3 = """            print("   color %02x: match=%.4f inkA=%d inkB=%d" %
                  (c, eq / tot, ia, ib))"""
new3 = """            meanA = sum(sum(row) for row in A) / 147456.0 * 255.0 / 3.0
            meanB = sum(sum(row) for row in B) / 147456.0 * 255.0 / 3.0
            print("   color %02x: match=%.4f inkA=%d inkB=%d vA=%.1f vB=%.1f" %
                  (c, eq / tot, ia, ib, meanA, meanB))"""
assert old3 in t2
t2 = t2.replace(old3, new3)
open(p2, "w", encoding="utf-8", newline="").write(t2)
print("validate script patched")
