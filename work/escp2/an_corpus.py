# -*- coding: utf-8 -*-
"""Corpus analyser: print structure + per-color ink footprints for oracle samples."""
import sys, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

def summarize(path, maxblocks=60):
    d = open(path, 'rb').read()
    job = P.parse_job(d, decode=True)
    print("=" * 110)
    print("FILE", path, "size", len(d))
    pm = P.prologue_map(job)
    print(" prologue:", {k: v for k, v in pm.items()})
    # prologue ESC(v)
    pv = [int.from_bytes(bytes.fromhex(c["payload"])[:4], 'little')
          for c in job.prologue if c["name"].startswith("ESC(v")]
    print(" prologue ESC(v):", pv)
    nb = len(job.blocks)
    recs = sum(len(b.records) for b in job.blocks)
    print(" blocks=%d records=%d" % (nb, recs))
    sig = collections.Counter(tuple("%02x" % r.color for r in b.records) for b in job.blocks)
    print(" block signatures:", dict(sig))
    adv = [b.advance for b in job.blocks]
    print(" advances:", adv[:30], "..." if len(adv) > 30 else "")
    print(" advance distinct:", collections.Counter(a for a in adv if a is not None).most_common(10))
    print(" n/m:", collections.Counter((r.n, r.m) for b in job.blocks for r in b.records))
    # per color footprint
    colors = []
    for b in job.blocks:
        for r in b.records:
            if r.color not in colors:
                colors.append(r.color)
    print(" color order (first block):", ["%02x" % r.color for r in job.blocks[0].records])
    for col in colors:
        tot_nz = 0
        blk_rows = []
        for b in job.blocks:
            rec = [r for r in b.records if r.color == col]
            if not rec:
                continue
            rec = rec[0]
            nzr = [i for i in range(rec.m) if any(rec.raw[i*rec.n:(i+1)*rec.n])]
            tot_nz += len(nzr)
            if nzr:
                blk_rows.append((b.index, nzr[0], nzr[-1], len(nzr), b.advance))
        print(" color 0x%02X: nonzero rows=%d ; blocks with ink=%d" % (col, tot_nz, len(blk_rows)))
        if len(blk_rows) <= maxblocks:
            # print compact
            txt = ", ".join("b%d[r%d..%d,%d,adv%s]" % t for t in blk_rows)
            print("    ", txt)
        else:
            print("     first:", blk_rows[:8])
            print("     last:", blk_rows[-8:])

if __name__ == '__main__':
    for p in sys.argv[1:]:
        summarize(p)
