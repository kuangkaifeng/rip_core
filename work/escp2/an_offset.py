# -*- coding: utf-8 -*-
"""Derive page-row offset per block: match union-ink raster rows against the
source image rows (718-bit masks) and vote for the page-row offset t (720dpi)."""
import sys, collections, hashlib
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P
from PIL import Image

GOLD = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"

im = Image.open(PNG).convert("RGBA")
W, H = im.size
px = im.load()
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
SCALE = 6

def dots_to_src(md):
    m = 0
    while md:
        lsb = md & -md
        x = lsb.bit_length() - 1
        m |= 1 << (x // SCALE)
        md ^= lsb
    return m

# union ink mask per (block,row)
union = {}
for b in job.blocks:
    for r in range(90):
        md = 0
        for rec in b.records:
            line = rec.raw[r*rec.n:(r+1)*rec.n]
            for i, byte in enumerate(line):
                if byte:
                    base = i*4
                    if (byte >> 6) & 3: md |= 1 << base
                    if (byte >> 4) & 3: md |= 1 << (base+1)
                    if (byte >> 2) & 3: md |= 1 << (base+2)
                    if byte & 3: md |= 1 << (base+3)
        if md:
            union[(b.index, r)] = md

print("rows with ink:", len(union))
# precompute source masks and per-row candidates (cache by hash of src mask)
cache = {}
cand_by_row = {}
for (k, r), md in union.items():
    src = dots_to_src(md)
    if src in cache:
        cand_by_row[(k, r)] = cache[src]
        continue
    scores = []
    for y in range(H):
        inter = (src & exp[y]).bit_count()
        uni = (src | exp[y]).bit_count()
        if uni:
            scores.append((inter/uni, y))
    scores.sort(reverse=True)
    cands = [(y, s) for s, y in scores[:4] if s > 0.4]
    cache[src] = cands
    cand_by_row[(k, r)] = cands

print("unique row masks:", len(cache))
# vote t per block: t so that page_row = t + r, page_row in [0, 3923], src row = page_row//6
for k in range(len(job.blocks)):
    votes = collections.Counter()
    for r in range(90):
        cands = cand_by_row.get((k, r))
        if not cands:
            continue
        for ysrc, sc in cands:
            w = sc
            for j in range(6):
                p = ysrc*6 + j
                t = p - r
                if -200 <= t <= 4000:
                    votes[t] += w
    if not votes:
        print("blk %2d: no data" % k); continue
    top = votes.most_common(8)
    print("blk %2d: total-w=%.1f top=%s" % (k, sum(votes.values()),
          [(t, round(w, 1)) for t, w in top]))
