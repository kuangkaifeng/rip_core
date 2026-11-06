#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract from .prs:
 1) all 8x256-double linearization LUTs per mode record -> CSV under reference/profiles/luts/
 2) mode record table (paths + linked modeId from colorCorrection queries) -> work/prs/mode_table.json
 3) ICC profile header/tag analysis -> work/prs/icc_analysis.json
"""
import os, sys, json, struct, glob, re

ROOT = r"D:\work\RIP核心分析"
OUT_LUT = os.path.join(ROOT, 'reference', 'profiles', 'luts')
OUT = os.path.join(ROOT, 'work', 'prs')

PRS = {
 'A3-DTF-1390': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\A3-DTF-1390.prs",
 'H13 XP600': r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\H13 XP600.prs",
}
# ICC files used (dist/bin/ICC Profile, CWD of mtripNet)
ICCS = {
 'SRGB IEC61966-2.1.icc': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\RGB\SRGB IEC61966-2.1.icc",
 'CoatedFOGRA39.icc': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\CMYK\CoatedFOGRA39.icc",
 'US Web Coated (SWOP) v2.icc': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\CMYK\US Web Coated (SWOP) v2.icc",
 'v1440x720-A3-DTF-1390.icm': os.path.join(ROOT, r'reference\profiles\source\OUTPUT\v1440x720-A3-DTF-1390.icm'),
 'v1440x1400-A3-DTF-1390.icm': os.path.join(ROOT, r'reference\profiles\source\OUTPUT\v1440x1400-A3-DTF-1390.icm'),
 'v2880x1400-A3-DTF-1390.icm': os.path.join(ROOT, r'reference\profiles\source\OUTPUT\v2880x1400-A3-DTF-1390.icm'),
 'v720x720-dtf.icm': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\OUTPUT\v720x720-dtf.icm",
 'v720x1080-dtf.icm': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\OUTPUT\v720x1080-dtf.icm",
 'v720x1440-dtf.icm': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\OUTPUT\v720x1440-dtf.icm",
 'v720x2160-dtf.icm': r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\ICC Profile\OUTPUT\v720x2160-dtf.icm",
}

def f64(d, o): return struct.unpack_from('<d', d, o)[0]
RAMP = struct.pack('<d', 1.0/255.0)

def find_luts(d):
    groups = []
    i = 0
    starts = []
    while True:
        i = d.find(RAMP, i)
        if i < 0: break
        st = i - 8
        if st >= 0 and f64(d, st) == 0.0:
            starts.append(st)
        i += 1
    for st in starts:
        if groups and st - (groups[-1][-1] + 256*8) in (12,):
            groups[-1].append(st)
        else:
            groups.append([st])
    return [g for g in groups if len(g) == 8]

def find_paths(d, lo, hi):
    pat = re.compile(rb'[A-Za-z0-9][A-Za-z0-9 _\-()./\\:]{2,}(?:\.icc|\.icm|\.mcm)\x00', re.I)
    out = []
    for m in pat.finditer(d, lo, hi):
        out.append(dict(off=m.start(), s=m.group()[:-1].decode('latin1')))
    return out

def main():
    os.makedirs(OUT_LUT, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    result = {}
    for tag, fn in PRS.items():
        d = open(fn, 'rb').read()
        luts = find_luts(d)
        recs = []
        for gi, g in enumerate(luts):
            lut_start = g[0]
            rec = dict(index=gi, lut_start=lut_start)
            # save LUT tables
            csvar = []
            for li, st in enumerate(g):
                vals = [f64(d, st + 8*k) for k in range(256)]
                csvar.append(f'ch{li}=' + ','.join(f'{v:.6f}' for v in vals))
            lp = os.path.join(OUT_LUT, f'{tag}_rec{gi}_linearization.csv')
            with open(lp, 'w', encoding='utf-8') as f:
                f.write('\n'.join(csvar))
            rec['lut_csv'] = os.path.relpath(lp, ROOT)
            # paths after LUTs
            nxt = luts[gi+1][0] if gi+1 < len(luts) else len(d)
            rec['paths'] = find_paths(d, g[-1]+256*8, min(nxt, g[-1]+256*8+7000))
            # opaque blob size: from previous record end to this lut start
            prev_end = None
            if gi > 0:
                prev = recs[gi-1]
                prev_paths_end = prev['paths'][-1]['off'] + 260
                prev_end = prev_paths_end
            rec['blob_est'] = (lut_start - prev_end) if prev_end else None
            recs.append(rec)
        result[tag] = dict(file=fn, size=len(d), records=recs)
        # attach modeId mapping from queries if available
    # mode query data
    qdir = os.path.join(ROOT, 'reference', 'jobs', 'queries')
    mode_map = {}
    for fn in glob.glob(os.path.join(qdir, 'icc_A3_m*.json')):
        q = json.load(open(fn, encoding='utf-8'))
        if 'mcm' in q:
            mode_map.setdefault('A3-DTF-1390', {})[q['id']] = q['mcm']
    for fn in glob.glob(os.path.join(qdir, 'icc_H13_m*.json')):
        q = json.load(open(fn, encoding='utf-8'))
        if 'mcm' in q:
            mode_map.setdefault('H13 XP600', {})[q['id']] = q['mcm']
    result['mode_icc_map'] = mode_map
    with open(os.path.join(OUT, 'mode_table.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print('saved -> work/prs/mode_table.json')
    for tag, r in result.items():
        if tag == 'mode_icc_map': continue
        print(f'{tag}: {len(r["records"])} records')
        for rec in r['records']:
            paths = [p['s'] for p in rec['paths']]
            print(f"  rec{rec['index']} lut_start=0x{rec['lut_start']:X} blob_est={rec['blob_est']} paths={paths[:4]}")
    # ICC analysis
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'prs_tools'))
    import icc_analyze
    icc_out = {}
    for name, path in ICCS.items():
        if not os.path.exists(path):
            icc_out[name] = dict(error='missing', path=path); continue
        d = open(path, 'rb').read()
        if d[36:40] != b'acsp':
            icc_out[name] = dict(error='not ICC', path=path); continue
        icc_out[name] = dict(path=path, size=len(d), header=icc_analyze.parse_header(d),
                             tags=[{k: t[k] for k in ('sig','type_','off','size')} for t in icc_analyze.parse_tags(d)])
    with open(os.path.join(OUT, 'icc_analysis.json'), 'w', encoding='utf-8') as f:
        json.dump(icc_out, f, indent=1, ensure_ascii=False)
    print('saved -> work/prs/icc_analysis.json')

if __name__ == '__main__':
    main()
