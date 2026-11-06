# -*- coding: utf-8 -*-
"""Per-pixel analysis of the overlapping copies of a page row (pass structure)."""
import sys, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

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

def analyze(path, col=0x00, prow=100):
    job = load(path)
    cum = cum_units(job)
    cumrow = [c // 8 for c in cum]
    n = job.blocks[0].records[0].n
    copies = collections.defaultdict(list)
    for b in job.blocks:
        for r in range(90):
            copies[cumrow[b.index] + r].append((b.index, r))
    print("=" * 90)
    print(path, "col %02x page row %d copies %s" % (col, prow, copies[prow]))
    rows = []
    for k, r in copies[prow]:
        rec = [x for x in b.records if x.color == col] if False else [x for x in job.blocks[k].records if x.color == col][0]
        rows.append((k, r, rec.raw[r*rec.n:(r+1)*rec.n]))
    for k, r, data in rows:
        c = collections.Counter(data)
        nz = sum(v for kk, v in c.items() if kk)
        print("  b%-2d r%-2d nz=%3d vals: %s" % (k, r, nz,
              " ".join("%02x:%d" % (kk, v) for kk, v in c.most_common(6))))
    # per-pixel stats over all pixels of the row (skip padded bytes? use all)
    cnt = collections.Counter(); mx = collections.Counter(); sm = collections.Counter()
    for i in range(n):
        for j in range(4):
            vs = [((data[i] >> (6-2*j)) & 3) for k, r, data in rows]
            cnt[sum(1 for v in vs if v)] += 1
            mx[max(vs)] += 1
            sm[sum(vs)] += 1
    print("  copies-with-nonzero hist:", sorted(cnt.items()))
    print("  max-value hist:", sorted(mx.items()))
    print("  SUM-value hist:", sorted(sm.items())[:20])
    # per-pixel tuples for a small slice in the middle
    print("  pixel tuples across %d copies (dots 400..410):" % len(rows))
    for i in range(100, 104):
        s = []
        for k, r, data in rows:
            b = data[i]
            s.append("%d%d%d%d" % (b >> 6 & 3, b >> 4 & 3, b >> 2 & 3, b & 3))
        print("    byte %d: %s" % (i, ' '.join(s)))

if __name__ == '__main__':
    analyze(r"D:\work\RIP核心分析\reference\prn_samples\a3dtf1390_flat_black_100_m2.prn", 0x00, 100)
    analyze(r"D:\work\RIP核心分析\reference\prn_samples\a3dtf1390_flat_black_100_m2.prn", 0x04, 100)
    analyze(r"D:\work\RIP核心分析\reference\prn_samples\a3dtf1390_flat_black_100_m2.prn", 0x00, 110)
