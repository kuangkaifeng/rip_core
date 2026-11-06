# -*- coding: utf-8 -*-
"""Verify: re-encode decoded raster with our RLE -> byte-identical to vendor RLE?"""
import sys, os, glob, collections
sys.path.insert(0, r"D:\work\RIP核心分析\tools\prn_tools")
import parse_prn as P

def test(path):
    d = open(path, 'rb').read()
    job = P.parse_job(d, decode=True)
    ok = bad = 0
    firstbad = None
    badstats = collections.Counter()
    for b in job.blocks:
        for rec in b.records:
            orig = d[rec.data_offset:rec.data_offset + rec.data_len]
            enc = P.rle_encode(rec.raw, rec.n)
            if enc == orig:
                ok += 1
            else:
                bad += 1
                if firstbad is None:
                    # find first difference
                    i = 0
                    while i < min(len(enc), len(orig)) and enc[i] == orig[i]:
                        i += 1
                    firstbad = (b.index, rec.color, rec.n, rec.m, i,
                                orig[max(0, i-4):i+12].hex(' '),
                                enc[max(0, i-4):i+12].hex(' '),
                                len(orig), len(enc))
                    badstats['lendiff'] = len(enc) - len(orig)
    print("%-52s records ok=%d bad=%d%s" % (os.path.basename(path), ok, bad,
          ("  firstbad=%s" % (firstbad,)) if firstbad else ""))
    if firstbad:
        print("     vendor bytes: %s" % firstbad[5])
        print("     our bytes   : %s" % firstbad[6])
    return ok, bad

if __name__ == '__main__':
    files = sys.argv[1:]
    if not files:
        B = r"D:\work\RIP核心分析\reference\prn_samples"
        files = [os.path.join(B, n + '.prn') for n in
                 ['a3dtf1390_flat_black_100_m2', 'a3dtf1390_flat_black_100_m0',
                  'a3dtf1390_checker_8px_720_m2', 'geomh_mode2', 'small64_mode2',
                  'a3dtf1390_grad_h_100_m2', 'a3dtf1390_lines_1px_100_m2']]
        files += [r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn",
                  r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\test.prn"]
    tot = [0, 0]
    for f in files:
        if os.path.exists(f):
            ok, bad = test(f)
            tot[0] += ok; tot[1] += bad
    print("TOTAL records: ok=%d bad=%d" % tuple(tot))
