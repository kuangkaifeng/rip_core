# -*- coding: utf-8 -*-
"""Analyze color swatch probes: which ESC i color code carries ink for K/W/C/M/Y/R/G/B."""
import sys, os, glob, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

BASE = r"D:\work\RIP核心分析\reference\prn_samples"

def an(path):
    d = open(path, 'rb').read()
    job = P.parse_job(d, decode=True)
    pm = P.prologue_map(job)
    cols = [r.color for r in job.blocks[0].records]
    print("=" * 90)
    print(os.path.basename(path), "blocks", len(job.blocks), "n/m",
          collections.Counter((r.n, r.m) for b in job.blocks for r in b.records),
          "ESC(S", pm.get('ESC_S'), "ESC(c", pm.get('ESC_c'), "ESC(e", pm.get('ESC_e'))
    print("   colors:", ["%02x" % c for c in cols])
    for col in cols:
        nz_rows = 0
        hist = collections.Counter()
        blocks_with = 0
        for b in job.blocks:
            rec = [r for r in b.records if r.color == col][0]
            nz = 0
            for r in range(rec.m):
                line = rec.raw[r*rec.n:(r+1)*rec.n]
                if any(line):
                    nz += 1
                    hist.update(line)
            nz_rows += nz
            blocks_with += 1 if nz else 0
        tot = sum(hist.values())
        print("   color 0x%02X: nonzero rows=%d blocks_with_ink=%d/%d total_bytes=%d topvals=%s" % (
            col, nz_rows, blocks_with, len(job.blocks), tot,
            [(hex(k), v) for k, v in hist.most_common(6)]))

for name in ['col_K_mode2', 'col_W_mode2', 'col_C_mode2', 'col_M_mode2', 'col_Y_mode2',
             'col_R_mode2', 'col_G_mode2', 'col_B_mode2']:
    p = os.path.join(BASE, name + '.prn')
    if os.path.exists(p):
        an(p)
    else:
        print("missing", p)
