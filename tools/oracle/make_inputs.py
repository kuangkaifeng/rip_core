#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate synthetic PNG inputs for the MainTop RIP oracle corpus.

Output: reference/inputs/*.png  (all files carry 120x120 dpi metadata so that
the job's view {xdpi:120,ydpi:120} matches the raster interpretation).

Run:  C:\\Espressif\\tools\\python\\python.exe tools\\oracle\\make_inputs.py
"""
import os
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reference", "inputs")
OUT = os.path.abspath(OUT)
DPI = (120, 120)

C = (0, 255, 255)
M = (255, 0, 255)
Y = (255, 255, 0)
K = (0, 0, 0)
R = (255, 0, 0)
G = (0, 255, 0)
B = (0, 0, 255)
W = (255, 255, 255)


def save(img, name):
    path = os.path.join(OUT, name)
    img.save(path, "PNG", dpi=DPI)
    print(f"{name:28s} {img.size[0]}x{img.size[1]} mode={img.mode} -> {os.path.getsize(path)} B")


def flat(size, color, name):
    save(Image.new("RGB", (size, size), color), name)


def quad(size, colors, name):
    """2x2 quadrants, order TL,TR,BL,BR."""
    img = Image.new("RGB", (size, size), W)
    d = size // 2
    for (x0, y0), col in zip([(0, 0), (d, 0), (0, d), (d, d)], colors):
        img.paste(col, (x0, y0, x0 + d, y0 + d))
    save(img, name)


def checker(size, cell, name):
    img = Image.new("RGB", (size, size), W)
    px = img.load()
    for y in range(size):
        for x in range(size):
            if ((x // cell) + (y // cell)) % 2:
                px[x, y] = K
    save(img, name)


def grad_h(size, name):
    img = Image.new("RGB", (size, size), W)
    px = img.load()
    for y in range(size):
        for x in range(size):
            v = round(x * 255 / (size - 1))
            px[x, y] = (v, v, v)
    save(img, name)


def grad_v(size, name):
    img = Image.new("RGB", (size, size), W)
    px = img.load()
    for y in range(size):
        for x in range(size):
            v = round(y * 255 / (size - 1))
            px[x, y] = (v, v, v)
    save(img, name)


def lines_1px(size, name):
    """Left half: 1px vertical black lines every 8px on white.
    Right half: 1px horizontal black lines every 8px on white."""
    img = Image.new("RGB", (size, size), W)
    px = img.load()
    for y in range(size):
        for x in range(size):
            if x < size // 2:
                if x % 8 == 0:
                    px[x, y] = K
            else:
                if y % 8 == 0:
                    px[x, y] = K
    save(img, name)


def alpha_checker(size, cell, name):
    """RGBA: opaque red / fully transparent alternating cells."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            if ((x // cell) + (y // cell)) % 2:
                px[x, y] = (255, 0, 0, 255)
            else:
                px[x, y] = (0, 0, 0, 0)
    save(img, name)


def alpha_grad(size, name):
    """RGBA: horizontal alpha ramp 0..255, solid blue RGB."""
    img = Image.new("RGBA", (size, size), (0, 0, 255, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            a = round(x * 255 / (size - 1))
            px[x, y] = (0, 0, 255, a)
    save(img, name)


def main():
    os.makedirs(OUT, exist_ok=True)
    # --- 64x64 quick probes ---
    flat(64, K, "flat_black_64.png")
    flat(64, W, "flat_white_64.png")
    flat(64, R, "flat_red_64.png")

    # --- 100x100 canonical set ---
    flat(100, K, "flat_black_100.png")
    flat(100, W, "flat_white_100.png")
    flat(100, C, "flat_c_100.png")
    flat(100, M, "flat_m_100.png")
    flat(100, Y, "flat_y_100.png")
    flat(100, K, "flat_k_100.png")
    flat(100, R, "flat_r_100.png")
    flat(100, G, "flat_g_100.png")
    flat(100, B, "flat_b_100.png")
    quad(100, [C, M, Y, K], "cmyk_quad_100.png")
    quad(100, [R, G, B, K], "rgb_quad_100.png")
    checker(100, 1, "checker_1px_100.png")
    checker(100, 8, "checker_8px_100.png")
    grad_h(100, "grad_h_100.png")
    grad_v(100, "grad_v_100.png")
    lines_1px(100, "lines_1px_100.png")
    alpha_checker(100, 16, "alpha_checker_100.png")
    alpha_grad(100, "alpha_grad_100.png")

    # --- 720x720 larger set (geometry / block alignment) ---
    flat(720, K, "flat_black_720.png")
    quad(720, [C, M, Y, K], "cmyk_quad_720.png")
    checker(720, 8, "checker_8px_720.png")
    grad_h(720, "grad_h_720.png")
    lines_1px(720, "lines_1px_720.png")

    print(f"\nDone. files in {OUT}")


if __name__ == "__main__":
    main()
