p = r"D:\work\RIP核心分析\tools\color_tools\build_rgb_cube17.py"
t = open(p, encoding="utf-8").read()
old = """    for y in range(y0, y0 + side, step):
        row = y * CONTENT + x0
        ty = (y % 1024) * 1024
        for x in range(x0, x0 + side, step):
            i = row + x
            ti = ty + (x % 1024)"""
new = """    base_y = y0
    for y in range(base_y, base_y + side, step):
        row = y * CONTENT
        ty = (y % 1024) * 1024
        for x in range(x0, x0 + side, step):
            i = row + x
            ti = ty + (x % 1024)"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("match_score fixed")
