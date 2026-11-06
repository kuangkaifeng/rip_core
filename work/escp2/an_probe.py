# -*- coding: utf-8 -*-
import sys, collections, hashlib
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

def load(path):
    d = open(path, 'rb').read()
    return P.parse_job(d, decode=True)

def cum_rows(job):
    """cumulative advance in units before each block, including prologue ESC(v)."""
    pro = [int.from_bytes(bytes.fromhex(c["payload"])[:4], 'little')
           for c in job.prologue if c["name"].startswith("ESC(v")]
    cum = []
    s = pro[0] if pro else 0
    for b in job.blocks:
        if b.advance is not None:
            s += b.advance
        cum.append(s)
    return cum

def analyze_flat(path):
    job = load(path)
    print("=" * 100); print(path)

def rowinfo(rec, r):
    line = rec.raw[r*rec.n:(r+1)*rec.n]
    nz = sum(1 for b in line if b)
    vals = collections.Counter(line)
    return nz, vals

def show(path, only_color=None, maxrows=200):
    job = load(path)
    cum = cum_rows(job)
    pm = P.prologue_map(job)
    print("=" * 100)
    print(path, " blocks", len(job.blocks), "ESC(D", pm.get('ESC_D'), "ESC(S", pm.get('ESC_S'), "ESC(c", pm.get('ESC_c'))
    print("cum rows (cum/8 floor):", [int(c // 8) for c in cum])
    colors = []
    for b in job.blocks:
        for r in b.records:
            if r.color not in colors:
                colors.append(r.color)
    for col in colors:
        if only_color is not None and col != only_color:
            continue
        print("-- color 0x%02X" % col)
        hashes = collections.Counter()
        for b in job.blocks:
            rec = [r for r in b.records if r.color == col][0]
            rows = []
            for r in range(rec.m):
                nz, vals = rowinfo(rec, r)
                if nz:
                    rows.append((r, nz, tuple(sorted(vals.items()))[:4]))
                    hashes[hashlib.sha1(rec.raw[r*rec.n:(r+1)*rec.n]).hexdigest()[:12]] += 1
            if rows:
                print("  blk %2d cumrow=%3d rows=%s" % (b.index, int(cum[b.index] // 8),
                      [(r, nz) for r, nz, _ in rows][:24]))
                if rows:
                    print("        first-row values:", rows[0][2])
        print("   unique row hashes:", len(hashes), " total rows:", sum(hashes.values()),
              " dup multiplicities:", collections.Counter(hashes.values()).most_common(6))

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'flat':
        show(r"D:\work\RIP核心分析\reference\prn_samples\a3dtf1390_flat_black_100_m2.prn")
    elif cmd == 'geomh':
        show(r"D:\work\RIP核心分析\reference\prn_samples\geomh_mode2.prn")
    elif cmd == 'geomv':
        show(r"D:\work\RIP核心分析\reference\prn_samples\geomv_mode2.prn")
    elif cmd == 'small64':
        show(r"D:\work\RIP核心分析\reference\prn_samples\small64_mode2.prn")
