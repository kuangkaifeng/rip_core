#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build/verify the RGB 9x9x9 -> device CMYK 3D LUT from the oracle rgb-cube probe.

Input:
  reference/prn_samples/probe_rgbcube9_540_m2.prn  (mode2, A3-DTF-1390.prs)
  reference/inputs/probe_rgbcube9_540.png          (540x540, 27x27 patches of 18px,
                                                     pitch 20px, levels 0..255 step ~32)
Screen model: reference/screen/final/thr_<ink>.bin (1024 tile, content-relative),
  level(v) = (v>=T1)+(v>=T2)+(v>=T3).
Method:
  1) decode PRN -> 3240x3240 content 2-bit planes for C,M,Y,K
     (page_row = pos_k + 8*r; content_top C/K=640, M/Y=644; 2bit MSB-first)
  2) for each patch take the center 10x10 image px (= 60x60 device dots) average level
  3) invert: per-window threshold histograms -> mean_level(v) curve for v=0..255,
     pick integer v minimizing |mean_level(v) - observed|
Output:
  reference/profiles/rgb_cube9.bin   ("RGB9" + u16 size + u8 ch + 4x729 u8, C,M,Y,K order)
  reference/profiles/rgb_cube9.json  (values + report)
Validation:
  probe_screen_rgb_ramps16_160_a3dtf1390_m2.prn vs rgb_ramps16_160.png:
  decode oracle -> invert ink; compare with trilinear-interpolated LUT prediction.
"""
import os, sys, json, struct, math, importlib.util, collections, time
from PIL import Image
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
INPUTS = os.path.join(ROOT, 'reference', 'inputs')
SCREEN = os.path.join(ROOT, 'reference', 'screen', 'final')
PROFILES = os.path.join(ROOT, 'reference', 'profiles')
WORK = os.path.join(ROOT, 'work', 'prs')
PARSE = os.path.join(ROOT, 'tools', 'prn_tools', 'parse_prn.py')
TILE = 1024
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
INK_ORDER = ['C', 'M', 'Y', 'K']
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}
LEVELS = [0, 32, 64, 96, 128, 160, 192, 224, 255]
UNPACK = [bytes(((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3)) for b in range(256)]
EXPAND = UNPACK

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def load_tile(ink):
    return open(os.path.join(SCREEN, f'thr_{ink}.bin'), 'rb').read()

def decode_content(prn_path, content_w, content_h, tops=TOP, verbose=True):
    """Decode PRN into {ink: 2D bytearray content_h x content_w} of 2-bit levels."""
    P = load_parser()
    d = open(prn_path, 'rb').read()
    t0 = time.time()
    job = P.parse_job(d, decode=True)
    canv = {ink: [bytearray(content_w) for _ in range(content_h)] for ink in INK_ORDER}
    pos = 0
    n = content_w // 4
    for blk in job.blocks:
        if blk.advance is not None:
            pos += blk.advance
        for rec in blk.records:
            ink = next((k for k, v in COLOR.items() if v == rec.color), None)
            if ink is None or not rec.raw:
                continue
            top = tops[ink]
            cv = canv[ink]
            rn = min(rec.n, n)
            for r in range(rec.m):
                page_row = pos + 8*r
                y = page_row - top
                if not (0 <= y < content_h):
                    continue
                chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                row = b''.join(EXPAND[b] for b in chunk[:rn])
                if len(row) < content_w:
                    row = row + b'\x00'*(content_w-len(row))
                cvy = cv[y]
                if not any(cvy):
                    cvy[:] = row
                else:
                    for x in range(content_w):
                        v = row[x]
                        if v > cvy[x]:
                            cvy[x] = v
    if verbose:
        print(f'  decoded {os.path.basename(prn_path)}: blocks={len(job.blocks)} in {time.time()-t0:.1f}s')
    return canv

class TileInverter:
    def __init__(self, ink):
        self.ink = ink
        self.tile = load_tile(ink)

    def window_hist(self, xs, ys):
        """Histogram of T1/T2/T3 over dot positions (x,y) lists."""
        tile = self.tile
        h1 = [0]*256; h2 = [0]*256; h3 = [0]*256
        for y in ys:
            base = (y % TILE)*TILE
            for x in xs:
                o = (base + (x % TILE))*3
                h1[tile[o]] += 1
                h2[tile[o+1]] += 1
                h3[tile[o+2]] += 1
        return h1, h2, h3

    def mean_curve(self, h1, h2, h3):
        """mean predicted level vs integer ink value 0..255 (T=0 counted as never)."""
        n = float(sum(h1)) or 1.0
        c1 = [0]*257; c2 = [0]*257; c3 = [0]*257
        for v in range(1, 256):
            c1[v] = c1[v-1] + h1[v]
            c2[v] = c2[v-1] + h2[v]
            c3[v] = c3[v-1] + h3[v]
        out = []
        for v in range(256):
            s = 0
            if v >= 1:
                s += c1[v] + c2[v] + c3[v]
            out.append(s / float(n))
        return out

    def invert(self, obs_mean):
        """Find v with predicted mean closest to observed; linear interpolation."""
        # window hist must be cached by caller; this method uses last set window
        raise NotImplementedError

def window_positions(x0_dots, y0_dots, w=60, h=60):
    xs = list(range(x0_dots, x0_dots + w))
    ys = list(range(y0_dots, y0_dots + h))
    return xs, ys

def build_cube_lut():
    # 1) decode cube PRN
    content = 540*6
    print(f'decoding rgbcube PRN (content {content}x{content}) ...', flush=True)
    canv = decode_content(os.path.join(SAMPLES, 'probe_rgbcube9_540_m2.prn'), content, content)
    inv = {ink: TileInverter(ink) for ink in INK_ORDER}
    # cache mean curves per window (window 60x60 at patch centers)
    values = {ink: [0]*729 for ink in INK_ORDER}
    residuals = {ink: [] for ink in INK_ORDER}
    t0 = time.time()
    for p in range(729):
        pr, pc = divmod(p, 27)
        img_x0 = 1 + 20*pc + 4   # center 10x10 image px
        img_y0 = 1 + 20*pr + 4
        x0 = img_x0 * 6
        y0 = img_y0 * 6
        xs = list(range(x0, x0 + 60))
        ys = list(range(y0, y0 + 60))
        for ink in INK_ORDER:
            cv = canv[ink]
            x0s = xs[0]; x0e = xs[-1]+1
            tot = 0
            for y in ys:
                tot += sum(cv[y][x0s:x0e])
            obs = tot / float(3600)
            w = inv[ink]
            h1, h2, h3 = w.window_hist(xs, ys)
            curve = w.mean_curve(h1, h2, h3)
            # find integer best
            best_v = min(range(256), key=lambda v: abs(curve[v]-obs))
            # refine with linear interpolation on the two neighbours
            vf = float(best_v)
            if best_v > 0 and curve[best_v-1] < curve[best_v]:
                lo_v, hi_v = best_v-1, best_v
            elif best_v < 255 and curve[best_v+1] > curve[best_v]:
                lo_v, hi_v = best_v, best_v+1
            else:
                lo_v = hi_v = best_v
            if hi_v != lo_v:
                d = curve[hi_v] - curve[lo_v]
                frac = (obs - curve[lo_v]) / d if d else 0.0
                vf = lo_v + max(0.0, min(1.0, frac))
            val = int(round(max(0.0, min(255.0, vf))))
            values[ink][p] = val
            residuals[ink].append(abs(curve[best_v]-obs))
        if p % 100 == 0:
            print(f'  patch {p}/729 ({time.time()-t0:.0f}s)', flush=True)
    # write bin
    out = bytearray()
    out += b'RGB9'
    out += struct.pack('<H', 9)
    out += bytes([4])
    for ink in INK_ORDER:
        out += bytes(values[ink])
    bin_path = os.path.join(PROFILES, 'rgb_cube9.bin')
    with open(bin_path, 'wb') as f:
        f.write(out)
    print(f'written {bin_path} ({len(out)} bytes)')
    # json report
    report = {}
    for ink in INK_ORDER:
        res = residuals[ink]
        report[ink] = dict(mean_abs_level_residual=sum(res)/len(res),
                           max_abs_level_residual=max(res),
                           value_min=min(values[ink]), value_max=max(values[ink]))
    js = dict(levels=LEVELS,
              order=[[LEVELS[i], LEVELS[j], LEVELS[k]] for i in range(9) for j in range(9) for k in range(9)][:729],
              inks=INK_ORDER,
              values={ink: values[ink] for ink in INK_ORDER},
              report=report,
              source='probe_rgbcube9_540_m2.prn via screen-tile inversion',
              format='RGB9 + u16 size=9 + u8 channels=4 + 4x729 u8 (C,M,Y,K), order r,g,b each 9 levels')
    with open(os.path.join(PROFILES, 'rgb_cube9.json'), 'w', encoding='utf-8') as f:
        json.dump(js, f, ensure_ascii=False)
    print('report:', json.dumps(report, indent=1))
    return values

def trilinear(values, r, g, b):
    """Predict ink values for arbitrary RGB via trilinear interpolation on the 9^3 grid."""
    # grid coordinate
    def coord(c):
        if c <= 0: return 0, 0.0
        if c >= 255: return 7, 1.0
        for i in range(8):
            if LEVELS[i] <= c <= LEVELS[i+1]:
                t = (c - LEVELS[i]) / float(LEVELS[i+1]-LEVELS[i])
                return i, t
        return 7, 1.0
    ri, rt = coord(r); gi, gt = coord(g); bi, bt = coord(b)
    out = []
    for ink in INK_ORDER:
        v = values[ink]
        def at(i, j, k):
            return v[(i*9 + j)*9 + k]
        c00 = at(ri, gi, bi)*(1-rt) + at(ri+1, gi, bi)*rt
        c01 = at(ri, gi, bi+1)*(1-rt) + at(ri+1, gi, bi+1)*rt
        c10 = at(ri, gi+1, bi)*(1-rt) + at(ri+1, gi+1, bi)*rt
        c11 = at(ri, gi+1, bi+1)*(1-rt) + at(ri+1, gi+1, bi+1)*rt
        c0 = c00*(1-gt) + c10*gt
        c1 = c01*(1-gt) + c11*gt
        out.append(c0*(1-bt) + c1*bt)
    return out

def invert_patch(canv, tops, img_x0, img_y0, inv, win=6):
    """Invert ink values for a flat region centered at image px (img_x0,img_y0), win x win px."""
    xs = list(range(img_x0*6, img_x0*6 + win*6))
    ys = list(range(img_y0*6, img_y0*6 + win*6))
    out = []
    for ink in INK_ORDER:
        cv = canv[ink]
        x0s = xs[0]; x0e = xs[-1]+1
        tot = 0
        for y in ys:
            tot += sum(cv[y][x0s:x0e])
        obs = tot / float(len(xs)*len(ys))
        w = inv[ink]
        h1, h2, h3 = w.window_hist(xs, ys)
        curve = w.mean_curve(h1, h2, h3)
        best_v = min(range(256), key=lambda v: abs(curve[v]-obs))
        out.append(best_v)
    return out

def validate_ramps():
    print('\n=== validation: rgb_ramps16_160 (independent probe) ===')
    content = 160*6
    canv = decode_content(os.path.join(SAMPLES, 'probe_screen_rgb_ramps16_160_a3dtf1390_m2.prn'),
                          content, content)
    im = Image.open(os.path.join(INPUTS, 'rgb_ramps16_160.png')).convert('RGB')
    px = im.load()
    inv = {ink: TileInverter(ink) for ink in INK_ORDER}
    # bands: rows 0-52 R, 53-105 G, 106-158 B; 16 columns of 10px, levels 17*k
    bands = [('R', 26), ('G', 79), ('B', 132)]
    errors = {ink: [] for ink in INK_ORDER}
    samples = []
    for name, ycen in bands:
        for k in range(16):
            xcen = k*10 + 5
            rgb = px[xcen, ycen]
            oracle = invert_patch(canv, TOP, xcen-3, ycen-3, inv, win=6)
            pred = trilinear(values_global, *rgb)
            row = []
            for i, ink in enumerate(INK_ORDER):
                d = oracle[i] - pred[i]
                errors[ink].append(d)
                row.append(f'{ink}:{oracle[i]:3d}/{pred[i]:6.1f}({d:+5.1f})')
            samples.append((name, k, rgb, row))
    # report
    for ink in INK_ORDER:
        e = errors[ink]
        ae = sorted(abs(x) for x in e)
        n = len(e)
        mean = sum(e)/n
        mae = sum(ae)/n
        p90 = ae[int(0.9*(n-1))]
        mx = max(ae)
        print(f'  {ink}: n={n} mean_err={mean:+.2f} MAE={mae:.2f} P90={p90:.1f} max={mx:.0f}')
    # print a few samples
    print('  samples (R band first 5):')
    for s in samples[:5]:
        print('   ', s[0], s[1], s[2], ' | '.join(s[3]))
    print('  samples (G band first 3):')
    for s in samples[16:19]:
        print('   ', s[0], s[1], s[2], ' | '.join(s[3]))
    # also dump full error samples
    with open(os.path.join(WORK, 'rgb_lut_validation.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(samples=[dict(band=s[0], level=s[1], rgb=s[2], detail=s[3]) for s in samples],
                       errors={ink: errors[ink] for ink in INK_ORDER}), f, indent=1, ensure_ascii=False)
    print('saved work/prs/rgb_lut_validation.json')

if __name__ == '__main__':
    values_global = build_cube_lut()
    # compare with lead's LUT (if overwritten by us, compare saved copy from before? skip)
    validate_ramps()
