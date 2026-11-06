from PIL import Image
p = r"D:\work\RIP核心分析\reference\inputs\rgb_ramps16_160.png"
im = Image.open(p).convert("RGB")
prev = None
for y in range(160):
    c = im.getpixel((155, y))
    if c != prev:
        print("y=%3d x=155 color=%s" % (y, c))
        prev = c
print("--- x=100 across y ---")
prev = None
for y in range(160):
    c = im.getpixel((100, y))
    if c != prev:
        print("y=%3d x=100 color=%s" % (y, c))
        prev = c
