# -*- coding: utf-8 -*-
"""Match every raster row of the golden PRN against source image rows to derive
the (block, row) -> page-row mapping."""
import sys, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P
from PIL import Image

GOLD = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"

im = Image.open(PNG).convert("RGBA")
W, H = im.size
px = im.load()
# expected ink row masks (bit x = ink at source pixel x) - union over all channels
exp = []
for y in range(H):
    m = 0
    for x in range(W):
        r, g, b, a = px[x, y]
        if a > 8 and not (r > 240 and g > 240 and b > 240):
            m |= (1 << x)
    exp.append(m)

d = open(GOLD, 'rb').read()
job = P.parse_job(d, decode=True)
print("blocks", len(job.blocks))

SCALE = 6   # 720 / 120
Wdots = 4308

def rowmask_to_src(mask_dots):
    """mask_dots: int with bit per dot (1080*4). Map dot -> source pixel (dot//6)."""
    m = 0
    # iterate set bits
    while mask_dots:
        lsb = mask_dots & -mask_dots
        x = lsb.bit_length() - 1
        m |= 1 << (x // SCALE)
        mask_dots ^= lsb
    return m

results = {}   # (block, color) -> list of (r, besty)
for b in job.blocks:
    for rec in b.records:
        rows = []
        for r in range(rec.m):
            line = rec.raw[r*rec.n:(r+1)*rec.n]
            if not any(line):
                continue
            # dots mask
            md = 0
            for i, byte in enumerate(line):
                if byte:
                    base = i*4
                    v = byte
                    md |= (1 if (v >> 6) & 3 else 0) << (base)
                    md |= (1 if (v >> 4) & 3 else 0) << (base+1)
                    md |= (1 if (v >> 2) & 3 else 0) << (base+2)
                    md |= (1 if v & 3 else 0) << (base+3)
            src = rowmask_to_src(md)
            # best match
            best = None; bestscore = -1
            for y in range(H):
                inter = (src & exp[y]).bit_count()
                uni = (src | exp[y]).bit_count()
                sc = inter/uni if uni else 0
                if sc > bestscore:
                    bestscore = sc; best = y
            rows.append((r, best, round(bestscore,3)))
        results[(b.index, rec.color)] = rows

# print summary: for each block, first color's rows -> source y
for col in [job.blocks[0].records[0].color]:
    print("=" * 100)
    print("color 0x%02X  (block -> list of (row, matched source_y, score))" % col)
    for b in job.blocks:
        rs = results[(b.index, col)]
        if not rs:
            print("blk %2d: (empty)" % b.index); continue
        # compress: separate runs of consecutive matched y?
        ys = [x[1] for x in rs]
        rsidx = [x[0] for x in rs]
        # print first/last and whether y sequence is monotonic
        mono = all(ys[i+1] >= ys[i] for i in range(len(ys)-1))
        print("blk %2d: n=%3d rows %d..%d  y %d..%d mono=%s  ylist=%s" %
              (b.index, len(rs), rsidx[0], rsidx[-1], ys[0], ys[-1], mono, ys[:20]))

import json
out = {("%d_%02X" % (k[0], k[1])): v for k, v in results.items()}
with open(r"D:\work\RIP核心分析\work\escp2\rowmatch.json", "w", encoding="utf-8") as f:
    json.dump(out, f)
print("saved rowmatch.json")
