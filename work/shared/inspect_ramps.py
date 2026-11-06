from PIL import Image
import os
p = r"D:\work\RIP核心分析\reference\inputs\rgb_ramps16_160.png"
im = Image.open(p).convert("RGB")
print("size", im.size, "dpi", im.info.get("dpi"))
# 打印若干采样行的颜色，猜测布局
for y in [0, 2, 8, 16, 40, 80, 120, 159]:
    row = [im.getpixel((x, y)) for x in [0, 8, 16, 32, 48, 80, 120, 159]]
    print("y=%3d" % y, row)
