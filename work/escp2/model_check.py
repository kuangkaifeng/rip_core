# -*- coding: utf-8 -*-
"""Systematic model checker: for each sample derive VSTEP/rowStep/colStep/P0 and verify."""
import sys, os, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P
from PIL import Image

def load(path):
    d = open(path, 'rb').read()
    return P.parse_job(d, decode=True)

def cum_units(job):
    pro = [int.from_bytes(bytes.fromhex(c["payload"])[:4], 'little')
           for c in job.prologue if c["name"].startswith("ESC(v")]
    cum = []; s = pro[0] if pro else 0
    for b in job.blocks:
        if b.advance is not None: s += b.advance
        cum.append(s)
    return cum

def check(path, png=None, content_rows=None, content_cols=None):
    job = load(path)
    pm = P.prologue_map(job)
    pos = cum_units(job)
    U = pm.get('ESC_U', {}); D = pm.get('ESC_D', {}); S = pm.get('ESC_S', {}); c = pm.get('ESC_c', {})
    pageunit = 2880 // U.get('a', 1) if U.get('a') else None
    VSTEP = 1440 // D.get('v', 1) if D.get('v') else None
    HSTEP = 1440 // D.get('h', 1) if D.get('h') else None
    # vertical units = pageunit (assume same); VSTEP in units
    VSTEP_units = D.get('v', 1) * pageunit // 1440 if D.get('v') else None
    print("=" * 100)
    print(os.path.basename(path), "blocks", len(job.blocks), "ESC(U", U, "ESC(D", D,
          "ESC(S", S, "ESC(c", c, "ESC(e", pm.get('ESC_e', {}).get('dot'))
    print("  pageunit", pageunit, "VSTEP_units", VSTEP_units, "HSTEP_dpi", HSTEP,
          "n/m", collections.Counter((r.n, r.m) for b in job.blocks for r in b.records),
          "colors", ["%02x" % r.color for r in job.blocks[0].records])
    print("  pos:", pos[:16], "..." if len(pos) > 16 else "")
    adv = collections.Counter(b.advance for b in job.blocks if b.advance is not None)
    print("  advances:", adv.most_common(8))
    # printed paper rows (all colors union)
    prows = collections.defaultdict(list)
    for b in job.blocks:
        for r in range(90):
            hit = False
            for rec in b.records:
                if any(rec.raw[r*rec.n:(r+1)*rec.n]):
                    hit = True; break
            if hit:
                prows[pos[b.index] + VSTEP_units * r].append(b.index)
    ps = sorted(prows)
    print("  printed paper rows: %d unique, range %s..%s" % (len(ps), ps[0], ps[-1]))
    print("  rows with 2+ blocks:", sum(1 for v in prows.values() if len(v) > 1))
    # residue check: each printed p must satisfy p ≡ pos_k mod VSTEP for its blocks
    bad = 0
    for p, ks in prows.items():
        for k in ks:
            if (p - pos[k]) % VSTEP_units != 0 or not (0 <= (p - pos[k]) // VSTEP_units < 90):
                bad += 1
    print("  residue/row-range violations:", bad)
    if png and os.path.exists(png):
        im = Image.open(png)
        W, H = im.size
        dpi = im.info.get('dpi', (72, 72))[0] or 72
        rowStep = pageunit / dpi
        colStep = (HSTEP * pageunit // 1440) / dpi if False else None
        # horizontal dots per image px = HSTEP_dpi / dpi  (HSTEP_dpi = 1440/h)
        colStep = HSTEP / dpi
        # vertical print rows per image px = pageunit / dpi
        print("  PNG %dx%d dpi=%.2f -> rowStep=%.4f colStep=%.4f" % (W, H, dpi, rowStep, colStep))
        expH = round(H * rowStep); expW = round(W * colStep)
        print("  expected content print height=%d  width dots=%d ; ESC(S)=%s (width=%d, height+M=%d)"
              % (expH, expW, S, S.get('width'), S.get('height')))
    if content_rows:
        # content_rows: list of image rows having content (known)
        p0s = []
        for i in content_rows[:5]:
            print("   image row", i, "-> expected paper rows", [p for p in range(0, 20000) if False])
    return job, pos, VSTEP_units, pm

if __name__ == '__main__':
    B = r"D:\work\RIP核心分析\reference\prn_samples"
    IN = r"D:\work\RIP核心分析\reference\inputs"
    for name in ['a3dtf1390_flat_black_100_m0', 'a3dtf1390_flat_black_100_m1',
                 'a3dtf1390_flat_black_100_m2', 'a3dtf1390_flat_black_100_m3',
                 'a3dtf1390_flat_black_64_m2', 'small64_mode2', 'a3dtf1390_flat_black_720_m2']:
        p = os.path.join(B, name + '.prn')
        png = None
        if name.startswith('a3dtf1390_flat_black_720'):
            png = os.path.join(IN, 'flat_black_720.png')
        elif name.startswith('a3dtf1390_flat_black_64'):
            png = os.path.join(IN, 'flat_black_64.png')
        elif name.startswith('a3dtf1390_flat_black_100'):
            png = os.path.join(IN, 'flat_black_100.png')
        elif name == 'small64_mode2':
            png = r"D:\work\RIP核心分析\work\escp2\probes\small64.png"
        if os.path.exists(p):
            check(p, png)
