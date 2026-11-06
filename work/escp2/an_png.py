# -*- coding: utf-8 -*-
from PIL import Image
import collections
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"
im = Image.open(PNG).convert("RGBA")
W, H = im.size
px = im.load()
print("size", W, H)
# classify pixels
cnt = collections.Counter()
red_rows = collections.Counter(); blue_rows = collections.Counter()
red_cols = collections.Counter(); blue_cols = collections.Counter()
alpha_hist = collections.Counter()
for y in range(H):
    for x in range(W):
        r, g, b, a = px[x, y]
        alpha_hist[a] += 1
        if a == 0:
            cnt['transparent'] += 1
            continue
        if r > 180 and g < 100 and b < 100:
            cnt['red'] += 1; red_rows[y] += 1; red_cols[x] += 1
        elif b > 120 and r < 100 and g < 100:
            cnt['blue'] += 1; blue_rows[y] += 1; blue_cols[x] += 1
        elif r > 230 and g > 230 and b > 230:
            cnt['white'] += 1
        else:
            cnt['other'] += 1
print("classes", cnt.most_common(10))
print("alpha distinct", sorted(alpha_hist.items(), key=lambda t:-t[1])[:6])
def rng(c):
    ks = sorted(k for k,v in c.items())
    return (ks[0], ks[-1], len(ks)) if ks else None
print("red rows", rng(red_rows), "red cols", rng(red_cols))
print("blue rows", rng(blue_rows), "blue cols", rng(blue_cols))
# row profile summary: for red, contiguous runs of rows
def runs(c):
    ks = sorted(c)
    out = []
    if not ks: return out
    s = ks[0]; p = ks[0]
    for k in ks[1:]:
        if k == p+1: p = k; continue
        out.append((s,p)); s = k; p = k
    out.append((s,p))
    return out
print("red row runs", runs(red_rows))
print("blue row runs", runs(blue_rows))
print("red col runs", runs(red_cols)[:10])
print("blue col runs", runs(blue_cols)[:10])
# x profile coarse
print("red cols min/max", min(red_cols), max(red_cols))
print("blue cols min/max", min(blue_cols), max(blue_cols))
# Save a downscaled mask preview
mask = Image.new("RGB", (W, H), (255,255,255))
mp = mask.load()
for y in range(H):
    for x in range(W):
        r,g,b,a = px[x,y]
        if a==0: mp[x,y]=(0,255,0)
        elif r>180 and g<100 and b<100: mp[x,y]=(255,0,0)
        elif b>120 and r<100 and g<100: mp[x,y]=(0,0,255)
        elif not (r>230 and g>230 and b>230): mp[x,y]=(128,128,128)
mask.save(r"D:\work\RIP核心分析\work\escp2\png_mask.png")
print("saved mask")
