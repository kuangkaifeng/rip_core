# -*- coding: utf-8 -*-
# 统一 v2 格式：magic "RGBL" + u16 size + u8 channels + u8 reserved + u8 grid[size] + data
# 修改两个构建脚本的输出部分
import re
p17 = r"D:\work\RIP核心分析\tools\color_tools\build_rgb_cube17.py"
t = open(p17, encoding="utf-8").read()
old = """out = bytearray(b"RGB9")
out += struct.pack("<H", N)
out += bytes([4])
for ink in INKS:
    out += bytes(vals[ink])"""
new = """out = bytearray(b"RGBL")
out += struct.pack("<H", N)
out += bytes([4, 0])
out += bytes(levels)          # 轴网格值（size 个）
for ink in INKS:
    out += bytes(vals[ink])"""
assert old in t
t = t.replace(old, new)
open(p17, "w", encoding="utf-8", newline="").write(t)
print("cube17 builder -> RGBL v2")

p9 = r"D:\work\RIP核心分析\tools\color_tools\build_rgb_cube9.py"
t = open(p9, encoding="utf-8").read()
old9 = """data = bytearray()
data += b"RGB9"
data += struct.pack("<H", N)
data += bytes([4])
for ink in INKS:
    data += bytes(vals[ink])"""
new9 = """data = bytearray()
data += b"RGBL"
data += struct.pack("<H", N)
data += bytes([4, 0])
data += bytes(levels)
for ink in INKS:
    data += bytes(vals[ink])"""
if old9 in t:
    t = t.replace(old9, new9)
    open(p9, "w", encoding="utf-8", newline="").write(t)
    print("cube9 builder -> RGBL v2")
