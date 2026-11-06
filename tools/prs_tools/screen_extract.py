#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract the halftone screen function from single-channel probe PRNs.

Probe: cmyk_probe_C<t>_64.tif (64x64 constant C=t) -> probe_screen_probe_C<t>_a3dtf1390_m2.prn
Geometry (verified): mode2 -> content plane rows 640..1023, cols 0..383 (384x384 device dots).
Screen model hypothesis H1: level(t,x,y) = floor(3*t + u(x,y)), t = ink/255, u = spatial field.
  -> per-pixel monotone in t; per-pixel u interval = [level-3t, level+1-3t)
Tests: monotonicity, interval consistency, periodicity, cross-channel phase.
"""
import os, sys, json, collections, math
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prs_tools")
import prn_canvas

ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
OUT = os.path.join(ROOT, 'reference', 'screen')
ROW0, ROW1 = 640, 1023
COL0, COL1 = 0, 383
COLOR = {'C': 0x00, 'K': 0x04, 'M': 0x12, 'Y': 0x11}

CTONES = [16*i for i in range(1, 16)]   # 16..240
OTHER = [0, 64, 128, 192, 255]

def load_probe(ch, tone):
    cands = [os.path.join(SAMPLES, f'probe_screen_probe_{ch}{tone}_a3dtf1390_m2.prn'), os.path.join(SAMPLES, f'probe_sweep_{ch}{tone}_a3dtf1390_m2.prn')]
    fn = next((c for c in cands if os.path.exists(c)), None)
    if fn is None:
        print(f'  {ch}{tone}: no PRN'); return None
    cvs, info = prn_canvas.decode_canvas(fn, vstep=8, verbose=False)
    cv = cvs.get(COLOR[ch])
    if cv is None:
        return None
    H = ROW1 - ROW0 + 1
    W = COL1 - COL0 + 1
    return [[cv[ROW0 + y][COL0 + x] for x in range(W)] for y in range(H)]

def main():
    os.makedirs(OUT, exist_ok=True)
    tones = [0] + CTONES + [255]
    mats = {}
    for t in tones:
        m = load_probe('C', t)
        if m is None:
            print(f'C{t}: missing PRN'); continue
        mats[t] = m
    present = sorted(mats)
    print('loaded C tones:', present)

    H = len(mats[present[0]]); W = len(mats[present[0]][0])
    print(f'content {W}x{H}')

    # 1) monotonicity per pixel
    viol = 0
    nonmono_pixels = 0
    for y in range(H):
        for x in range(W):
            prev = -1
            ok = True
            for t in present:
                v = mats[t][y][x]
                if v < prev:
                    ok = False; viol += 1
                prev = v
            if not ok: nonmono_pixels += 1
    print(f'monotonic violations={viol} pixels={nonmono_pixels}/{W*H} ({nonmono_pixels*100.0/(W*H):.2f}%)')

    # 2) u intervals per pixel (H1)
    empty = 0
    widths = collections.Counter()
    u_mid = [[0.0]*W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            lo, hi = 0.0, 1.0
            for t in present:
                v = mats[t][y][x]
                tt = t/255.0
                lo = max(lo, v - 3*tt)
                hi = min(hi, v + 1 - 3*tt)
            if hi <= lo:
                empty += 1
                u_mid[y][x] = (lo+hi)/2
            else:
                u_mid[y][x] = (lo+hi)/2
                widths[round(hi-lo, 2)] += 1
    print(f'H1 interval empty={empty} ({empty*100.0/(W*H):.3f}%)')
    print('interval width distribution (top):', widths.most_common(12))

    # 3) periodicity of u field: for candidate P, group (x%P,y%P), compute residual variance
    print('\n-- periodicity test: variance of u within phase classes --')
    print('   (lower = more periodic; compare with total variance)')
    vals = [u_mid[y][x] for y in range(H) for x in range(W)]
    mean = sum(vals)/len(vals)
    tot_var = sum((v-mean)**2 for v in vals)/len(vals)
    print(f'   total variance={tot_var:.6f} std={math.sqrt(tot_var):.4f}')
    best = []
    for P in (4, 8, 16, 32, 64, 96, 128, 192, 256, 384):
        groups = collections.defaultdict(list)
        for y in range(H):
            for x in range(W):
                groups[(x % P, y % P)].append(u_mid[y][x])
        var = 0.0; n = 0; sizes = []
        for g in groups.values():
            m = sum(g)/len(g)
            var += sum((v-m)**2 for v in g); n += len(g)
            sizes.append(len(g))
        var /= n
        best.append((var, P, len(groups), min(sizes), max(sizes)))
        print(f'   P={P:3d}: phase classes={len(groups):5d} samples/class {min(sizes)}..{max(sizes)} '
              f'within-var={var:.6f} (ratio {var/tot_var:.4f})')
    best.sort()
    print('best period by variance:', best[0])

    # 4) save u midpoints + raw; also per-tone coverage for reference
    with open(os.path.join(OUT, 'u_field_C.bin'), 'wb') as f:
        for y in range(H):
            f.write(bytes(min(255, max(0, round(u_mid[y][x]*255))) for x in range(W)))
    meta = dict(source='probe_screen_probe_C*_a3dtf1390_m2.prn', geometry=dict(row0=ROW0, row1=ROW1, col0=COL0, col1=COL1, w=W, h=H),
                tones=present, empty_intervals=empty, mono_viol=viol,
                u_field=dict(file='u_field_C.bin', format='8-bit unsigned, row-major, value=round(u*255), w*h=%dx%d' % (W,H)),
                period_test=[dict(P=p, var=v, classes=c, minn=mn, maxn=mx) for v,p,c,mn,mx in best])
    with open(os.path.join(OUT, 'screen_analysis.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    print('\nsaved -> reference/screen/{u_field_C.bin,screen_analysis.json}')
    # coverage table per tone
    print('\n-- tone -> level stats (content) --')
    for t in present:
        h = [0,0,0,0]
        for y in range(H):
            for x in range(W):
                h[mats[t][y][x]] += 1
        n = W*H
        print(f'  t={t:3d} (3t={3*t/255:.3f}): level hist={h} mean={sum(i*h[i] for i in range(4))/n:.4f} '
              f'coverage={sum(i*h[i] for i in range(4))/n/3:.4f}')

if __name__ == '__main__':
    main()

