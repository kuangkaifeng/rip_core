#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T6-B/C: generate screening / linearization probe images.

CMYK TIFF (PIL mode "CMYK", embedded 120 dpi):
  cmyk_ramp16_160x160.tif   4 ink bands (C,M,Y,K top->bottom), each a 16-step
                            horizontal ramp 0,17,34,...,255
  cmyk_patch20_100x100.tif  single-ink patch matrix: rows C/M/Y/K (25px),
                            cols levels 0/64/128/192/255 (20px)
  cmyk_white_100x100.tif    all ink 0
  cmyk_full_100x100.tif     all ink 255 (full overprint)
  cmyk_probe_<ink><val>_64.tif  one solid patch per ink/value (for mtcount)
RGB PNG (for T3 chain):
  rgb_gray16_160x160.png    16-step horizontal gray ramp 0..255
  rgb_ramps16_160x160.png   R,G,B ink bands, 16-step ramps

Run: python tools/oracle/make_screen_probes.py
"""
import os
from PIL import Image

OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "..", "reference", "inputs"))
DPI = (120, 120)
INKS = ["C", "M", "Y", "K"]
LEVELS = [round(i * 255 / 15) for i in range(16)]     # 0,17,34,...,255


def cmyk_pixel(ink, v):
    """ink: C/M/Y/K, v: 0..255 (ink amount)."""
    c = m = y = k = 0
    if ink == "C":
        c = v
    elif ink == "M":
        m = v
    elif ink == "Y":
        y = v
    elif ink == "K":
        k = v
    return (c, m, y, k)


def make_ramp(path):
    w = h = 160
    band = h // 4
    step = w // 16
    img = Image.new("CMYK", (w, h), (0, 0, 0, 0))
    px = img.load()
    for row, ink in enumerate(INKS):
        for x in range(w):
            v = LEVELS[min(x // step, 15)]
            c, m, y, k = cmyk_pixel(ink, v)
            for yy in range(row * band, (row + 1) * band):
                px[x, yy] = (c, m, y, k)
    img.save(path, "TIFF", dpi=DPI)
    print("wrote", path, os.path.getsize(path))


def make_patch_matrix(path):
    levels = [0, 64, 128, 192, 255]
    bw, bh = 20, 25
    img = Image.new("CMYK", (100, 100), (0, 0, 0, 0))
    px = img.load()
    for row, ink in enumerate(INKS):
        for col, v in enumerate(levels):
            c, m, y, k = cmyk_pixel(ink, v)
            for x in range(col * bw, (col + 1) * bw):
                for yy in range(row * bh, (row + 1) * bh):
                    px[x, yy] = (c, m, y, k)
    img.save(path, "TIFF", dpi=DPI)
    print("wrote", path, os.path.getsize(path))


def make_solid(path, ink="K", v=0, size=64):
    img = Image.new("CMYK", (size, size), cmyk_pixel(ink, v))
    img.save(path, "TIFF", dpi=DPI)
    print("wrote", path, os.path.getsize(path))


def make_rgb_gray(path):
    w = h = 160
    step = w // 16
    img = Image.new("RGB", (w, h), (0, 0, 0))
    px = img.load()
    for x in range(w):
        v = LEVELS[min(x // step, 15)]
        for y in range(h):
            px[x, y] = (v, v, v)
    img.save(path, "PNG", dpi=DPI)
    print("wrote", path, os.path.getsize(path))


def make_rgb_ramps(path):
    w = h = 160
    band = h // 3
    step = w // 16
    img = Image.new("RGB", (w, h), (0, 0, 0))
    px = img.load()
    for row, ch in enumerate((0, 1, 2)):
        for x in range(w):
            v = LEVELS[min(x // step, 15)]
            rgb = [0, 0, 0]
            rgb[ch] = v
            for y in range(row * band, (row + 1) * band):
                px[x, y] = tuple(rgb)
    img.save(path, "PNG", dpi=DPI)
    print("wrote", path, os.path.getsize(path))


def main():
    os.makedirs(OUT, exist_ok=True)
    make_ramp(os.path.join(OUT, "cmyk_ramp16_160.tif"))
    make_patch_matrix(os.path.join(OUT, "cmyk_patch20_100.tif"))
    make_solid(os.path.join(OUT, "cmyk_white_100.tif"), "K", 0, 100)
    make_solid(os.path.join(OUT, "cmyk_full_100.tif"), "K", 255, 100)
    # full overprint: all four inks 255 -> use a dedicated function
    img = Image.new("CMYK", (100, 100), (255, 255, 255, 255))
    img.save(os.path.join(OUT, "cmyk_full4_100.tif"), "TIFF", dpi=DPI)
    print("wrote", os.path.join(OUT, "cmyk_full4_100.tif"))
    # single solid patches for dot-size statistics (mtcount)
    for ink in INKS:
        for v in (0, 64, 128, 192, 255):
            make_solid(os.path.join(OUT, f"cmyk_probe_{ink}{v}_64.tif"), ink, v, 64)
    # RGB probes (task C)
    make_rgb_gray(os.path.join(OUT, "rgb_gray16_160.png"))
    make_rgb_ramps(os.path.join(OUT, "rgb_ramps16_160.png"))
    print("done")


if __name__ == "__main__":
    main()
