from PIL import Image
p = r"D:\work\RIP核心分析\reference\inputs\rgb_ramps16_160.png"
im = Image.open(p).convert("RGB")
prev = None
for y in range(160):
    c = im.getpixel((5, y))
    if c != prev:
        print("y=%3d x=5 color=%s" % (y, c))
        prev = c
print("--- x changes at y=20 ---")
prev = None
for x in range(0, 160, 1):
    c = im.getpixel((x, 20))
    if c != prev:
        print("x=%3d color=%s" % (x, c))
        prev = c
