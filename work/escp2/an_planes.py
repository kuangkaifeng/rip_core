# -*- coding: utf-8 -*-
import sys, collections, os
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P
from PIL import Image

GOLD = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
OUT = r"D:\work\RIP核心分析\work\escp2\planes"
os.makedirs(OUT, exist_ok=True)
d = open(GOLD, 'rb').read()
job = P.parse_job(d, decode=True)
adv0 = 150
for c in job.prologue:
    if c["name"].startswith("ESC(v"):
        adv0 = int.from_bytes(bytes.fromhex(c["payload"])[:4], 'little')
print("adv0", adv0)

# record data lengths
print("\n per-block record RLE data_len (bytes): blk  adv   [color:len x4]")
for b in job.blocks:
    print("  %2d %4s  %s" % (b.index, b.advance, "  ".join("%02x:%5d" % (r.color, r.data_len) for r in b.records)))

colors = sorted({r.color for b in job.blocks for r in b.records})
# raw stacked plane images: width=4320, height=49*90
for col in colors:
    rows = []
    for b in job.blocks:
        rec = [r for r in b.records if r.color == col][0]
        for r in range(rec.m):
            line = rec.raw[r * rec.n:(r + 1) * rec.n]
            rows.append(P.unpack2bit_msb(line))
    img = Image.new("L", (len(rows[0]), len(rows)))
    img.putdata(b"".join(bytes((v * 85) for v in row) for row in rows))
    img = img.resize((len(rows[0]) // 4, len(rows) // 4), Image.BILINEAR)
    img.save(os.path.join(OUT, "stack_%02x.png" % col))
    print("saved stack_%02x.png" % col, img.size)

# combined color image, naive stack: 0x11->red, 0x00->green, 0x12->blue, 0x04->white
combo = Image.new("RGB", (4320, 49 * 90), (0, 0, 0))
cmap = {0x11: (255, 0, 0), 0x00: (0, 255, 0), 0x12: (0, 0, 255), 0x04: (255, 255, 0)}
cp = combo.load()
for b in job.blocks:
    for rec in b.records:
        c = cmap.get(rec.color)
        if not c: continue
        for r in range(rec.m):
            dots = P.unpack2bit_msb(rec.raw[r * rec.n:(r + 1) * rec.n])
            y = b.index * 90 + r
            for x, v in enumerate(dots):
                if v:
                    cp[x, y] = (cp[x, y][0] | c[0], cp[x, y][1] | c[1], cp[x, y][2] | c[2])
combo = combo.resize((4320 // 4, 49 * 90 // 4), Image.BILINEAR)
combo.save(os.path.join(OUT, "combo_stack.png"))
print("saved combo_stack.png")
