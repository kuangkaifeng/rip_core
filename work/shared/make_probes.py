# -*- coding: utf-8 -*-
import os
from PIL import Image
WS = r"D:\work\RIP核心分析"
outdir = os.path.join(WS, "reference", "inputs")
os.makedirs(outdir, exist_ok=True)

# 1) 用户测试图（无 DPI）拷入
src = os.path.join(WS, "work", "shared", "print_debug", "test22.jpg")
dst = os.path.join(outdir, "print_debug_test22.jpg")
Image.open(src).save(dst, quality=95)
print("test22 ->", dst, Image.open(dst).size)

# 2) RGB 9^3 立方体色块探针（18px 块 + 2px 间隔，27x27 网格 = 540x540 @120dpi）
levels = [0, 32, 64, 96, 128, 160, 192, 224, 255]
PITCH = 20; PATCH = 18
N = 9
img = Image.new("RGB", (27 * PITCH, 27 * PITCH), (255, 255, 255))
idx = 0
mapping = []
for ri, r in enumerate(levels):
    for gi, g in enumerate(levels):
        for bi, b in enumerate(levels):
            col = idx % 27; row = idx // 27
            x0 = col * PITCH + 1; y0 = row * PITCH + 1
            for yy in range(PATCH):
                for xx in range(PATCH):
                    img.putpixel((x0 + xx, y0 + yy), (r, g, b))
            mapping.append((r, g, b))
            idx += 1
cube = os.path.join(outdir, "probe_rgbcube9_540.png")
img.save(cube, dpi=(120, 120))
print("rgbcube ->", cube, img.size, "patches:", len(mapping))
import json
json.dump({"levels": levels, "pitch": PITCH, "patch": PATCH, "grid": 27,
           "order": mapping}, open(os.path.join(WS, "reference", "inputs", "probe_rgbcube9_meta.json"), "w"))
print("meta saved")
