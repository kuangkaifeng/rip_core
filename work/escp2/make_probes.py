# -*- coding: utf-8 -*-
"""Generate controlled probe PNGs for the MainTop oracle (protocol-analyst runs them).

Design goals:
  geomh: 1-px horizontal black lines at known image rows on transparent bg
         -> reveals exact (image row) -> (block, row) mapping
  geomv: 1-px vertical black lines at known image cols -> reveals x -> byte/bit mapping
  small64: edge rows/cols of a non-multiple-of-8 image -> rounding rules
  colors: solid patches -> ESC i color code -> ink channel
  dots: single black pixels -> bit order / horizontal alignment
"""
import os
from PIL import Image

BASE = r"D:\work\RIP核心分析\work\escp2\probes"
os.makedirs(BASE, exist_ok=True)
BLACK = (0, 0, 0, 255)

def new(w, h, bg=(0, 0, 0, 0)):
    return Image.new("RGBA", (w, h), bg)

# ---- geomh: horizontal lines at rows 61,183,305,427,549,671 (720x720) ----
im = new(720, 720)
p = im.load()
for y in (61, 183, 305, 427, 549, 671):
    for x in range(60, 660):
        p[x, y] = BLACK
im.save(os.path.join(BASE, "geomh.png"))

# ---- geomv: vertical lines at cols 61,183,305,427,549,671 ----
im = new(720, 720)
p = im.load()
for x in (61, 183, 305, 427, 549, 671):
    for y in range(60, 660):
        p[x, y] = BLACK
im.save(os.path.join(BASE, "geomv.png"))

# ---- small64: 64x64 edge lines (top/bottom row, left/right col) ----
im = new(64, 64)
p = im.load()
for x in range(64):
    p[x, 0] = BLACK
    p[x, 63] = BLACK
for y in range(64):
    p[0, y] = BLACK
    p[63, y] = BLACK
im.save(os.path.join(BASE, "small64.png"))

# ---- small63: 63x61 to check odd sizes ----
im = new(63, 61)
p = im.load()
for x in range(63):
    p[x, 0] = BLACK
    p[x, 60] = BLACK
for y in range(61):
    p[0, y] = BLACK
    p[62, y] = BLACK
im.save(os.path.join(BASE, "small63.png"))

# ---- rows1x: 720x720 with ONLY one 1px line at y=400 (simplest vertical probe) ----
im = new(720, 720)
p = im.load()
for x in range(100, 620):
    p[x, 400] = BLACK
im.save(os.path.join(BASE, "row400.png"))

# ---- colors: 100x100 solid opaque patches ----
cols = dict(K=(0, 0, 0), W=(255, 255, 255), C=(0, 255, 255), M=(255, 0, 255),
            Y=(255, 255, 0), R=(255, 0, 0), G=(0, 255, 0), B=(0, 0, 255))
for name, c in cols.items():
    im = new(100, 100, bg=(c[0], c[1], c[2], 255))
    im.save(os.path.join(BASE, "col_%s.png" % name))

# ---- half block: left half black, right half transparent (for x mapping) ----
im = new(720, 720)
p = im.load()
for y in range(60, 660):
    for x in range(0, 360):
        p[x, y] = BLACK
im.save(os.path.join(BASE, "halfblock.png"))

# ---- dots: 5 isolated pixels ----
im = new(720, 720)
p = im.load()
for (x, y) in [(100, 100), (300, 200), (500, 300), (120, 500), (600, 600)]:
    p[x, y] = BLACK
im.save(os.path.join(BASE, "dots.png"))

# ---- grayscale ramp rows: 16 blocks of 45 rows at distinct gray levels (720x720) ----
im = new(720, 720)
p = im.load()
for blk in range(16):
    g = int(255 * blk / 15)
    for y in range(blk * 45, blk * 45 + 45):
        for x in range(720):
            p[x, y] = (g, g, g, 255)
im.save(os.path.join(BASE, "grayramp16.png"))

print("written to", BASE)
for f in sorted(os.listdir(BASE)):
    print(" ", f, os.path.getsize(os.path.join(BASE, f)))
