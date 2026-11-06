#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_preview.py -- reconstruct a page image from a MainTop/ESC-P2 .prn
using the verified geometry model, and save PNG/BMP previews.

Model (see docs/prn_escp2.md):
    page_unit  = 2880 / ESC(U.a                 (units per inch; mode2/3 = 720)
    VSTEP      = ESC(U... ) = ESC(D.v * page_unit / 1440   (page units between
                 consecutive raster rows *within* a block; 8 for mode2/3)
    paper_row(k, r) = pos_k + VSTEP * r          (pos_k = cumulative ESC(v))
    page row of the raster image = P0 + row (content placed at P0)
    page col of dot x         = x (0-based, 4 dots/byte, MSB pair first)

Usage:
  python render_preview.py job.prn --out preview.png [--scale 4]
                               [--plane all|0x00|0x04|...]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_prn as P
from PIL import Image

# measured content origin P0 (page units) per mode signature
P0_TABLE = {
    # (page_unit, VSTEP, advance, ncolors): P0
    (360, 4, 71, 4): 288,    # mode0
    (360, 4, 35, 6): 324,    # mode1
    (720, 8, 79, 4): 640,    # mode2
    (720, 8, 39, 6): 680,    # mode3
    (720, 8, 11, 6): 712,    # mode5
    (1440, 16, 11, 6): 1413,  # mode7/9
}


def mode_signature(job):
    pm = P.prologue_map(job)
    U = pm.get("ESC_U", {}); D = pm.get("ESC_D", {})
    page_unit = 2880 // U.get("a", 1) if U.get("a") else 720
    vstep = D.get("v", 16) * page_unit // 1440 if D.get("v") else 8
    adv = [b.advance for b in job.blocks if b.advance is not None]
    adv = adv[0] if adv else 79
    ncol = len(job.blocks[0].records) if job.blocks else 0
    return page_unit, vstep, adv, ncol, pm


def cum_units(job):
    pro = [int.from_bytes(bytes.fromhex(c["payload"])[:4], "little")
           for c in job.prologue if c["name"].startswith("ESC(v")]
    cum = []; s = pro[0] if pro else 0
    for b in job.blocks:
        if b.advance is not None:
            s += b.advance
        cum.append(s)
    return cum


def render(job, plane="all", scale=4, bg=(255, 255, 255)):
    page_unit, vstep, adv, ncol, pm = mode_signature(job)
    p0 = P0_TABLE.get((page_unit, vstep, adv, ncol), 0)
    pos = cum_units(job)
    n = job.blocks[0].records[0].n
    colors = [r.color for r in job.blocks[0].records]
    # paper row -> {(color, byte_index) -> value}
    rows = {}
    for b in job.blocks:
        for rec in b.records:
            for r in range(rec.m):
                line = rec.raw[r * rec.n:(r + 1) * rec.n]
                if not any(line):
                    continue
                p = pos[b.index] + vstep * r
                cur = rows.setdefault(p, {})
                cur[rec.color] = line
    if not rows:
        return None, dict(page_unit=page_unit, vstep=vstep, p0=p0)
    pmin = min(rows); pmax = max(rows)
    W = n * 4
    H = pmax - pmin + 1
    # channel -> RGB display colour
    disp = {0x04: (0, 0, 0), 0x00: (0, 200, 255), 0x12: (255, 0, 255),
            0x11: (255, 255, 0), 0x01: (220, 220, 220), 0x02: (120, 120, 120)}
    img = Image.new("RGB", (W, H), bg)
    px = img.load()
    for p, byc in rows.items():
        y = p - pmin
        for col, line in byc.items():
            if plane != "all" and plane != "0x%02X" % col and plane != "0x%02x" % col:
                continue
            c = disp.get(col, (128, 128, 128))
            for i, byte in enumerate(line):
                if not byte:
                    continue
                base = i * 4
                for k in range(4):
                    v = (byte >> (6 - 2 * k)) & 3
                    if v:
                        px[base + k, y] = c
    if scale > 1:
        img = img.resize((max(1, W // scale), max(1, H // scale)), Image.LANCZOS)
    return img, dict(page_unit=page_unit, vstep=vstep, p0=p0, pmin=pmin, pmax=pmax,
                     width_dots=W, colors=["%02x" % c for c in colors],
                     blocks=len(job.blocks))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("prn")
    ap.add_argument("--out", default="preview.png")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--plane", default="all")
    args = ap.parse_args(argv)
    d = open(args.prn, "rb").read()
    job = P.parse_job(d, decode=True)
    img, info = render(job, plane=args.plane, scale=args.scale)
    if img is None:
        print("no raster content"); return 1
    img.save(args.out)
    print(json_dumps := __import__("json").dumps(info, ensure_ascii=False))
    print("saved", args.out, img.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
