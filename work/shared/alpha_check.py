from PIL import Image
p = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"
im = Image.open(p)
print("mode:", im.mode, "size:", im.size)
if im.mode in ("RGBA","LA"):
    a = im.getchannel("A")
    from collections import Counter
    c = Counter(a.getdata())
    print("alpha hist top:", c.most_common(5), "total", im.size[0]*im.size[1])
    print("transparent ratio:", c[0]/ (im.size[0]*im.size[1]) if 0 in c else 0)
