# -*- coding: utf-8 -*-
"""Validate the paper-row model on the golden pair: build page raster and compare to source PNG."""
import sys, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P
from PIL import Image

GOLD = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"
VSTEP = 8

def cum_units(job):
    pro = [int.from_bytes(bytes.fromhex(c["payload"])[:4], 'little')
           for c in job.prologue if c["name"].startswith("ESC(v")]
    cum = []; s = pro[0] if pro else 0
    for b in job.blocks:
        if b.advance is not None: s += b.advance
        cum.append(s)
    return cum

d = open(GOLD, 'rb').read()
job = P.parse_job(d, decode=True)
pos = cum_units(job)
print("prologue pos:", pos[:3], "... blocks", len(job.blocks))
colors = [r.color for r in job.blocks[0].records]
print("colors", ["%02x" % c for c in colors])
n = job.blocks[0].records[0].n
print("n", n, "m", job.blocks[0].records[0].m)

# build paper row -> [(k,r)] map, and page raster per color
prow_map = collections.defaultdict(list)
for b in job.blocks:
    for r in range(90):
        prow_map[pos[b.index] + VSTEP * r].append((b.index, r))

print("paper rows covered:", min(prow_map), "..", max(prow_map), "count", len(prow_map))
dups = {p: v for p, v in prow_map.items() if len(v) > 1}
print("rows with multiple blocks:", len(dups), "max copies", max(len(v) for v in prow_map.values()))
print("sample dups:", list(dups.items())[:5])

# image geometry
im = Image.open(PNG).convert("RGBA")
W, H = im.size
print("image", W, H, "dpi", im.info.get('dpi'))
rowStep = 6      # 720/120
colStep = 6
P0 = 640
print("expected paper rows:", P0, "..", P0 + rowStep * H - 1)
covered = set(prow_map)
missing = [p for p in range(P0, P0 + rowStep * H) if p not in covered]
print("missing paper rows in image range:", len(missing), missing[:20])

# reconstruct page raster per color: dict color -> list of rows (each row = list of dot values)
# page width dots = n*4
page = {}
for col in colors:
    page[col] = {}
for b in job.blocks:
    for rec in b.records:
        for r in range(rec.m):
            p = pos[b.index] + VSTEP * r
            line = rec.raw[r*rec.n:(r+1)*rec.n]
            if not any(line):
                continue
            if p in page[rec.color]:
                old = page[rec.color][p]
                # OR combine (record duplicates)
                page[rec.color][p] = bytes(a | b2 for a, b2 in zip(old, line))
            else:
                page[rec.color][p] = line
print("reconstructed rows per color:", {("%02x" % c): len(page[c]) for c in colors})

# Render: page height = P0 + rowStep*H, width = n*4 dots
Wdots = n * 4
PH = P0 + rowStep * H
for col in colors:
    img = Image.new("L", (Wdots, PH), 0)
    px = img.load()
    for p, line in page[col].items():
        for i, byte in enumerate(line):
            if not byte: continue
            base = i * 4
            for k in range(4):
                v = (byte >> (6 - 2 * k)) & 3
                if v:
                    px[base + k, p] = 85 * v
    img = img.crop((0, P0, Wdots, PH))
    img = img.resize((Wdots // 6, (PH - P0) // 6), Image.BILINEAR)
    img.save(r"D:\work\RIP核心分析\work\escp2\gold_%02x.png" % col)
    print("saved gold_%02x.png" % col, img.size)

# Combined RGB: assign colors to channels for eyeballing: Y=0x04, K=0x00, LC=0x12, LM=0x11
rgb = Image.new("RGB", (Wdots // 6, (PH - P0) // 6), (255, 255, 255))
rp = rgb.load()
cmap = {0x04: (255, 255, 0), 0x00: (0, 0, 0), 0x12: (0, 160, 255), 0x11: (255, 0, 255)}
for col in colors:
    c = cmap.get(col, (128, 128, 128))
    for p, line in page[col].items():
        yy = (p - P0) // 6
        if not (0 <= yy < rgb.size[1]): continue
        for i, byte in enumerate(line):
            if not byte: continue
            base = i * 4
            for k in range(4):
                v = (byte >> (6 - 2 * k)) & 3
                if v:
                    xx = (base + k) // 6
                    if 0 <= xx < rgb.size[0]:
                        # blend
                        old = rp[xx, yy]
                        rp[xx, yy] = tuple(min(255, old[j] + (c[j] - 255) // 3) for j in range(3))
rgb.save(r"D:\work\RIP核心分析\work\escp2\gold_combo.png")
print("saved gold_combo.png", rgb.size)
