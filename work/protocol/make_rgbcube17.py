#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the 17^3 RGB cube probe PNG + meta JSON (T6 for RGB->ink 3D LUT).

Layout (same convention as the 9^3 probe `probe_rgbcube9_540.png`):
  levels  t = round(i*255/16), i=0..16  -> 17 levels
  grid    71x71 cells (=5041 >= 17^3=4913), pitch 16 px, patch 14x14 px
  order   r-major, g, b-minor:  idx = r*17*17 + g*17 + b
          cell  col = idx % 71, row = idx // 71
          patch origin (col*16+1, row*16+1)
  image   1136x1136, saved as PNG with dpi=(120,120)
          (mode2 content = image * 720/120 = 6816x6816)
Unused cells (indices >= 4913, i.e. bottom 128 cells) are filled mid-gray.

Outputs:
  reference/inputs/probe_rgbcube17_1136.png
  reference/inputs/probe_rgbcube17_meta.json
"""
import json
import os

from PIL import Image, ImageDraw

WS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", ".."))
OUT = os.path.join(WS, "reference", "inputs")
LEVELS = [int(round(i * 255.0 / 16.0)) for i in range(17)]
PITCH, PATCH, GRID = 16, 14, 71
SIZE = GRID * PITCH          # 1136
N = len(LEVELS)              # 17


def main():
    os.makedirs(OUT, exist_ok=True)
    order = [(LEVELS[r], LEVELS[g], LEVELS[b])
             for r in range(N) for g in range(N) for b in range(N)]
    img = Image.new("RGB", (SIZE, SIZE), (128, 128, 128))
    px = img.load()
    for idx, (r, g, b) in enumerate(order):
        col, row = idx % GRID, idx // GRID
        x0, y0 = col * PITCH + 1, row * PITCH + 1
        for y in range(y0, y0 + PATCH):
            for x in range(x0, x0 + PATCH):
                px[x, y] = (r, g, b)
    png = os.path.join(OUT, "probe_rgbcube17_1136.png")
    img.save(png, "PNG", dpi=(120, 120))
    meta = {
        "name": "probe_rgbcube17_1136",
        "image_size": [SIZE, SIZE],
        "dpi": [120, 120],
        "levels": LEVELS,
        "n_levels": N,
        "pitch": PITCH,
        "patch": PATCH,
        "grid": GRID,
        "grid_size": GRID * GRID,
        "n_patches": len(order),
        "order": order,
        "order_index": "idx = r*17*17 + g*17 + b (r-major, b-minor)",
        "cell_pos": "col = idx % 71, row = idx // 71",
        "patch_origin": "x0 = col*16 + 1, y0 = row*16 + 1 (14x14 px)",
        "content_scale": 6,
        "note": "same convention as probe_rgbcube9_540.png; unused grid cells are mid-gray",
    }
    mj = os.path.join(OUT, "probe_rgbcube17_meta.json")
    with open(mj, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))
    print("levels:", LEVELS)
    print("patches:", len(order), "grid:", GRID, "size:", SIZE,
          "png bytes:", os.path.getsize(png), "meta bytes:", os.path.getsize(mj))


if __name__ == "__main__":
    main()
