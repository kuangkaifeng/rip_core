#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extra input images with non-120 embedded DPI metadata.

Used to decide whether the rip `view` parameter overrides the PNG's own DPI for
image inputs (A3-DTF-1390 mode 2).  Pixels are identical to cmyk_quad_100.png;
only the PNG pHYs chunk (dpi) differs.

Run: python tools/oracle/make_inputs_dpi.py
"""
import os
from PIL import Image

OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "..", "reference", "inputs"))

C, M, Y, K = (0, 255, 255), (255, 0, 255), (255, 255, 0), (0, 0, 0)


def quad(size, colors):
    img = Image.new("RGB", (size, size), (255, 255, 255))
    d = size // 2
    for (x0, y0), col in zip([(0, 0), (d, 0), (0, d), (d, d)], colors):
        img.paste(col, (x0, y0, x0 + d, y0 + d))
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    img = quad(100, [C, M, Y, K])
    for dpi in (72, 300):
        name = os.path.join(OUT, f"cmyk_quad_100_dpi{dpi}.png")
        img.save(name, "PNG", dpi=(dpi, dpi))
        print(name, os.path.getsize(name))
    # same pixel content, different embedded dpi -> identical pixel hash
    print("done")


if __name__ == "__main__":
    main()
