# -*- coding: utf-8 -*-
"""Test whether the ~9 copies of a page row (in overlapping blocks) are complementary."""
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

def rowof(job, k, col, r):
    rec = [x for x in job.blocks[k].records if x.color == col][0]
    return rec.raw[r*rec.n:(r+1)*rec.n]

def test(path, col=0x04, page_rows=None):
    job = load(path)
    cum = cum_units(job)
    cumrow = [c // 8 for c in cum]
    n = job.blocks[0].records[0].n
    print("=" * 100); print(path, "blocks", len(job.blocks), "n", n)
    print("cumrow:", cumrow)
    # collect copies: page_row -> [(k, r)]
    copies = collections.defaultdict(list)
    for b in job.blocks:
        for r in range(90):
            copies[cumrow[b.index] + r].append((b.index, r))
    if page_rows:
        for p in page_rows:
            print("page row %d : copies at %s" % (p, copies.get(p)))
            if p not in copies: continue
            datas = [(k, r, rowof(job, k, col, r)) for k, r in copies[p]]
            # compute OR, AND, count per dot
            orv = bytearray(n); andv = bytearray([0xFF]*n); sums = [0]*(n*4)
            for k, r, data in datas:
                nz = sum(1 for b in data if b)
                print("   (b%d,r%d) nonzero_bytes=%d hist=%s" % (k, r, nz,
                      collections.Counter(data).most_common(4)))
                for i, b in enumerate(data):
                    orv[i] |= b; andv[i] &= b
                    for kk in range(4):
                        sums[i*4+kk] += (b >> (6-2*kk)) & 3
            print("   OR nz bytes=%d  AND nz=%d" % (sum(1 for b in orv if b), sum(1 for b in andv if b)))
            print("   dot value sum hist (over copies):", collections.Counter(sums).most_common(8))
            # show a dot run in a region
            i0 = next(i for i, b in enumerate(orv) if b)
            print("   OR bytes [%d..%d]: %s" % (i0, i0+12, bytes(orv[i0:i0+12]).hex(' ')))
            for k, r, data in datas[:3]:
                print("      b%d r%d bytes: %s" % (k, r, data[i0:i0+12].hex(' ')))

if __name__ == '__main__':
    test(r"D:\work\RIP核心分析\reference\prn_samples\geomh_mode2.prn",
         page_rows=[156, 157, 309, 310])
