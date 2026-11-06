import sys, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

GOLD = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
d = open(GOLD,'rb').read()
job = P.parse_job(d, decode=True)
print("blocks", len(job.blocks))
# move prologue ESC(v) into block 0 advance
for c in job.prologue:
    if c["name"].startswith("ESC(v"):
        blk = bytes.fromhex(c["payload"])
        print("prologue ESC(v) =", int.from_bytes(blk[:4],'little'))

colors = sorted({r.color for b in job.blocks for r in b.records})
print("colors", [hex(c) for c in colors])

for col in colors:
    print("="*90)
    print("COLOR 0x%02X" % col)
    hist = collections.Counter()
    rows_with = []
    for b in job.blocks:
        rec = [r for r in b.records if r.color==col][0]
        raw = rec.raw
        nzrows = [r for r in range(rec.m) if any(raw[r*rec.n:(r+1)*rec.n])]
        rows_with.append(nzrows)
        hist.update(raw)
    print("byte value hist (top 10):", hist.most_common(10))
    print("total bytes non-zero:", sum(v for k,v in hist.items() if k), "of", sum(hist.values()))
    # for each block: row coverage and col range
    for bi, nzr in enumerate(rows_with):
        if not nzr:
            print("  blk %2d rows: (empty)" % bi)
            continue
        rec = [r for r in job.blocks[bi].records if r.color==col][0]
        raw = rec.raw
        cols = []
        for r in nzr:
            line = raw[r*rec.n:(r+1)*rec.n]
            nzc = [i for i,v in enumerate(line) if v]
            cols.append((nzc[0], nzc[-1], len(nzc)))
        print("  blk %2d rows: %3d [%d..%d] colrange %d..%d" % (bi, len(nzr), nzr[0], nzr[-1],
            min(c[0] for c in cols), max(c[1] for c in cols)))
