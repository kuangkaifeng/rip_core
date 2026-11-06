# -*- coding: utf-8 -*-
"""Validate §7.4 solver: k(p) = largest k with pos_k = p (mod VSTEP), pos_k<=p, r<=89.
Check on vendor corpus: for non-overlap rows the vendor's (k,r) must equal solver's."""
import sys, os
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

def load(path):
    d = open(path, 'rb').read()
    return P.parse_job(d, decode=True)

def setup(job):
    pm = P.prologue_map(job)
    U = pm['ESC_U']; D = pm['ESC_D']
    pageunit = 2880 // U['a']
    vstep = D['v'] * pageunit // 1440
    pro = [int.from_bytes(bytes.fromhex(c["payload"])[:4], 'little')
           for c in job.prologue if c["name"].startswith("ESC(v")]
    pos = []; s = pro[0] if pro else 0
    for b in job.blocks:
        if b.advance is not None: s += b.advance
        pos.append(s)
    adv = pos[1] - pos[0] if len(pos) > 1 else 0
    return vstep, pos, adv, pageunit

def inv_mod(a, m):
    for x in range(1, m):
        if (a * x) % m == 1:
            return x
    return None

def solve(p, pos0, adv, vstep, maxr=89):
    m = vstep
    k0 = ((p - pos0) * inv_mod(adv % m, m)) % m
    # largest k = k0 + m*t with pos0+adv*k <= p
    if pos0 + adv * k0 > p:
        return None
    t = (p - pos0 - adv * k0) // (adv * m)
    k = k0 + m * t
    if k < 0 or pos0 + adv * k > p:
        return None
    r = (p - pos0 - adv * k) // vstep
    if r > maxr:
        return None
    return k, r

def check(path):
    job = load(path)
    vstep, pos, adv, pageunit = setup(job)
    rows = {}
    for b in job.blocks:
        for r in range(90):
            hit = False
            for rec in b.records:
                if any(rec.raw[r*rec.n:(r+1)*rec.n]):
                    hit = True; break
            if hit:
                p = pos[b.index] + vstep * r
                rows.setdefault(p, []).append((b.index, r))
    total = len(rows); multi = sum(1 for v in rows.values() if len(v) > 1)
    # for rows covered by exactly one block, solver must match
    ok = bad = 0
    badsample = []
    for p, lst in rows.items():
        sol = solve(p, pos[0], adv, vstep)
        if len(lst) == 1:
            k, r = lst[0]
            if sol == (k, r):
                ok += 1
            else:
                bad += 1
                if len(badsample) < 5: badsample.append((p, lst[0], sol))
    # predicted block count N = 1+max k over content rows
    N = 1 + max(solve(p, pos[0], adv, vstep)[0] for p in rows if solve(p, pos[0], adv, vstep))
    print("%-52s rows=%d multi=%d  solver_ok=%d bad=%d  N_pred=%d N_actual=%d %s" % (
        os.path.basename(path), total, multi, ok, bad, N, len(job.blocks),
        "" if bad == 0 else "badsample=%s" % badsample))
    return N, len(job.blocks)

if __name__ == '__main__':
    B = r"D:\work\RIP核心分析\reference\prn_samples"
    names = ['a3dtf1390_flat_black_100_m0', 'a3dtf1390_flat_black_100_m1',
             'a3dtf1390_flat_black_100_m2', 'a3dtf1390_flat_black_100_m3',
             'a3dtf1390_flat_black_100_m5', 'a3dtf1390_flat_black_100_m7',
             'a3dtf1390_flat_black_100_m9', 'small64_mode2', 'geomh_mode2',
             'geomv_mode2', 'a3dtf1390_checker_8px_720_m2', 'col_K_mode2',
             'a3dtf1390_lines_1px_100_m2', 'a3dtf1390_grad_h_100_m0']
    for n in names:
        p = os.path.join(B, n + '.prn')
        if os.path.exists(p):
            check(p)
    for p in [r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"]:
        check(p)
