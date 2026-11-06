# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

GOLD = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
d = open(GOLD, 'rb').read()
job = P.parse_job(d, decode=True)

def getrow(block, color, r):
    rec = [x for x in job.blocks[block].records if x.color == color][0]
    line = rec.raw[r*rec.n:(r+1)*rec.n]
    vals = []
    for b in line:
        vals.append((b >> 6) & 3); vals.append((b >> 4) & 3)
        vals.append((b >> 2) & 3); vals.append(b & 3)
    return vals

# dot pattern in a dense area: block 34, color 0x00, row 40, x dots 1300..
for blk, row in [(34, 40), (35, 40), (33, 40), (34, 41)]:
    v = getrow(blk, 0x00, row)
    seg = v[1300:1420]
    print("blk %d row %d dots[1300:1420]: %s" % (blk, row, ''.join(str(x) for x in seg)))
    nz = sum(1 for x in v if x)
    print("   nonzero dots=%d/%d (%.3f)  value hist=%s" % (nz, len(v),
          nz/len(v), {k: v.count(k) for k in range(4)}))

# same page row from different blocks? use mapping page=page_off+r with off=150+
advs = [150]
s = 150
for b in job.blocks[1:]:
    s += b.advance
    advs.append(s)
print("cumulative offsets:", advs[:5], "...", advs[-4:])

# check overlap rows: block k rows 79..89 vs block k+1 rows 0..10
for k in (10, 20, 30, 34):
    print("=== overlap block %d rows 79..89 vs block %d rows 0..10" % (k, k+1))
    for r in range(79, 90):
        v1 = getrow(k, 0x00, r)
        for r2 in range(0, 11):
            v2 = getrow(k+1, 0x00, r2)
            # compare as masks
            m1 = sum(1 << i for i, x in enumerate(v1) if x)
            m2 = sum(1 << i for i, x in enumerate(v2) if x)
            if m1 == m2 and m1:
                print("   block%d row%d == block%d row%d (both nonzero)" % (k, r, k+1, r2))
