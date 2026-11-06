# -*- coding: utf-8 -*-
"""Find duplicate raster rows across blocks to derive vertical interleave."""
import sys, collections, hashlib
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

GOLD = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
d = open(GOLD, 'rb').read()
job = P.parse_job(d, decode=True)

# hash of (color, rowbytes)
loc = collections.defaultdict(list)
for b in job.blocks:
    for rec in b.records:
        for r in range(rec.m):
            line = rec.raw[r*rec.n:(r+1)*rec.n]
            if not any(line):
                continue
            h = hashlib.sha1(bytes([rec.color]) + line).hexdigest()[:16]
            loc[h].append((rec.color, b.index, r))

multi = {h: v for h, v in loc.items() if len(v) > 1}
print("nonzero rows:", sum(len(v) for v in loc.values()), " distinct hashes:", len(loc),
      " hashes with duplicates:", len(multi))
# distribution of duplicate multiplicities
print("multiplicity hist:", collections.Counter(len(v) for v in multi.values()).most_common(10))
# show some examples
for h, v in list(multi.items())[:25]:
    print("  ", h, v[:8])
# for each color separately
for col in sorted({r.color for b in job.blocks for r in b.records}):
    loc2 = collections.defaultdict(list)
    for b in job.blocks:
        rec = [r for r in b.records if r.color == col][0]
        for r in range(rec.m):
            line = rec.raw[r*rec.n:(r+1)*rec.n]
            if not any(line):
                continue
            loc2[hashlib.sha1(line).hexdigest()[:16]].append((b.index, r))
    m2 = {h: v for h, v in loc2.items() if len(v) > 1}
    print("color 0x%02X: rows=%d distinct=%d dup-hashes=%d mult=%s"
          % (col, sum(len(v) for v in loc2.values()), len(loc2), len(m2),
             collections.Counter(len(v) for v in m2.values()).most_common(6)))
    for h, v in list(m2.items())[:10]:
        print("     ", h, v)
