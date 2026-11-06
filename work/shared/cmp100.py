import os, importlib.util
WS = r"D:\work\RIP核心分析"
spec = importlib.util.spec_from_file_location("ve", os.path.join(WS, "tools", "validate", "validate_e2e.py"))
ve = importlib.util.module_from_spec(spec); spec.loader.exec_module(ve)
A = ve.decode_page(os.path.join(WS, "reference", "prn_samples", "a3dtf1390_flat_black_100_m2.prn"), content=600)
B = ve.decode_page(os.path.join(WS, "work", "shared", "e2e", "ours_a3dtf1390_flat_black_100_m2.prn"), content=600)
print("colors:", [hex(c) for c in A], [hex(c) for c in B])
for c in (0x04, 0x00, 0x12, 0x11):
    a = A.get(c); b = B.get(c)
    if not a or not b: continue
    eq = tot = 0; ia = ib = 0
    for y in range(600):
        ra, rb = a[y], b[y]
        for x in range(600):
            va, vb = ra[x], rb[x]
            if va: ia += 1
            if vb: ib += 1
            if va == vb: eq += 1
            tot += 1
    print("color %02x: match=%.4f inkA=%d inkB=%d meanA=%.1f meanB=%.1f" % (c, eq/tot, ia, ib, ia/147456*0+ (sum(sum(r) for r in a)/360000.0*255/3), (sum(sum(r) for r in b)/360000.0*255/3)))
