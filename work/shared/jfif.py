d = open(r"D:\work\RIP核心分析\reference\inputs\print_debug_test22.jpg","rb").read(200)
i = d.find(b"JFIF")
print("JFIF at", i)
if i >= 0:
    seg = d[i:i+14]
    print("segment:", seg.hex(' '))
    # JFIF: 'JFIF\0' major minor units xdensity(2) ydensity(2)
    units = seg[7]; xd = (seg[8]<<8)|seg[9]; yd = (seg[10]<<8)|seg[11]
    print("units=", units, "xdensity=", xd, "ydensity=", yd)
# 是否有 EXIF dpi
j = d.find(b"Exif")
print("Exif at", j)
