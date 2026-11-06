# -*- coding: utf-8 -*-
import sys, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

def load(path):
    d = open(path, 'rb').read()
    return P.parse_job(d, decode=True)

def cum_rows(job):
    pro = [int.from_bytes(bytes.fromhex(c["payload"])[:4], 'little')
           for c in job.prologue if c["name"].startswith("ESC(v")]
    cum = []; s = pro[0] if pro else 0
    for b in job.blocks:
        if b.advance is not None: s += b.advance
        cum.append(s)
    return cum

def row_extent(rec, r):
    line = rec.raw[r*rec.n:(r+1)*rec.n]
    nz = [i for i, b in enumerate(line) if b]
    if not nz: return None
    # dot extent from first/last nonzero byte with value detail
    vals = collections.Counter(line)
    # first nonzero byte value and first nonzero dot bit
    def first_dot(byte, base):
        for k in range(4):
            v = (byte >> (6-2*k)) & 3
            if v: return base+k, v
        return None
    def last_dot(byte, base):
        for k in range(3, -1, -1):
            v = (byte >> (6-2*k)) & 3
            if v: return base+k, v
        return None
    fd = first_dot(line[nz[0]], nz[0]*4)
    ld = last_dot(line[nz[-1]], nz[-1]*4)
    return dict(nz_bytes=len(nz), first_byte=nz[0], last_byte=nz[-1],
                first_dot=fd, last_dot=ld, nbytes=len(line),
                distinct=len(vals), hist=vals.most_common(6))

def show(path):
    job = load(path)
    cum = cum_rows(job)
    pm = P.prologue_map(job)
    print("=" * 100)
    print(path)
    print(" ESC(U", pm.get('ESC_U'), "ESC(D", pm.get('ESC_D'), "ESC(S", pm.get('ESC_S'),
          "ESC(c", pm.get('ESC_c'), "blocks", len(job.blocks))
    print(" n/m:", collections.Counter((r.n, r.m) for b in job.blocks for r in b.records))
    print(" colors:", ["%02x" % r.color for r in job.blocks[0].records])
    cols = [r.color for r in job.blocks[0].records]
    for col in cols:
        print("-- color 0x%02X" % col)
        for b in job.blocks[:12]:
            rec = [r for r in b.records if r.color == col][0]
            rows = []
            for r in range(rec.m):
                e = row_extent(rec, r)
                if e: rows.append((r, e))
            if rows:
                print("  blk %2d cum=%3d:" % (b.index, int(cum[b.index]//8)), end=" ")
                for r, e in rows[:6]:
                    print("r%d[nz=%d,x=%d..%d,dot=%s..%s,n=%d]" % (
                        r, e['nz_bytes'], e['first_byte'], e['last_byte'],
                        e['first_dot'], e['last_dot'], e['nbytes']), end=" ")
                print()

if __name__ == '__main__':
    for p in sys.argv[1:]:
        show(p)
