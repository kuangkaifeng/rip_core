#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MainTop .prs parser (reverse-engineered).

Structure (v3 '03 00 00 00' A3-DTF-1390 / v4 '04 00 00 00' H13 XP600):
  0x00  u32 magic 0x6E5344D0  (bytes D0 44 53 6E = "MtDS"? little-endian)
  0x04  u32 format version (3 = A3-DTF-1390, 4 = H13 XP600)
  0x08  u32 0x701 / 0x704? flags
  0x0C  u32 header-size candidate 0x160 (352)
  0x10  u32 0x01800000 / 0x01800001? -> u16 pair (0,0x180) or (0x8000,1)
  0x14  char[] driver module name "MtDummy.pdv" (NUL terminated, padded)
  ...   fixed header block (mode table pointers, MAC/serial, reserved 0x40..)
  ~0x5540 (A3) text config block: NUL-terminated printable entries, e.g.
        "A3-DTF-1390", "ExtendWpkNameC=eps1k4.wpk", "OutputFixedLines=90",
        "StochasticHalftone=00000601", "SetInkOrder=00000702",
        "Manufacturer = procolored", "SkipUnsupportSpotColor=1", "common.mcm",
        "v720x360dpi" ... "v2880x1440dpi", "UseMtCount=0", "DotSize:", ...
        then the driver's full option-name catalogue (PrintMedia/Ink/Speed/...).
  Then N mode records. Each record (A3: 3 records, H13: 4 records):
     [opaque per-mode blob  ~16.5-17.6 KB]   (unknown; screen/VSD/ICC cache)
     [8 x 256 double identity linearization LUTs, 12-byte gaps]  = 16468 B
     [optional 116-byte VSD/dot table]
     [96-byte mode config struct]
     [4 x char[260] ICC path records]  (group A)
     [88-byte struct]
     [4 x char[260] ICC path records]  (group B)   stride 0x104, 260=MAX_PATH
  Tail: "Manufacturer=inksonic" + driver names.

ICC path record order (verified by queryIccpath responses):
     [0] srcRgbPath      e.g. "SRGB IEC61966-2.1.icc"
     [1] srcCmykPath     e.g. "CoatedFOGRA39.icc" / "US Web Coated (SWOP) v2.icc"
     [2] mcmPath         "commnew.mcm"
     [3] destCmykPath    e.g. "v1440x720-A3-DTF-1390.icm"
"""
from __future__ import annotations
import sys, os, json, struct, re

DEFAULT_PRSS = [
    r"D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\A3-DTF-1390.prs",
    r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\H13 XP600.prs",
    r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\H13 XP600_myicc.prs",
]
ROOT = r"D:\work\RIP核心分析"
OUTDIR = os.path.join(ROOT, 'work', 'prs')

def u32(d, o): return struct.unpack_from('<I', d, o)[0]
def f64(d, o): return struct.unpack_from('<d', d, o)[0]
def cstr(d, o, n):
    b = d[o:o+n]
    z = b.find(b'\x00')
    if z >= 0: b = b[:z]
    return b.decode('latin1', 'replace')

# ---- known constants -------------------------------------------------------
MAGIC = 0x6E5344D0
RAMP_DOUBLE = struct.pack('<d', 1.0/255.0)   # 10..70 3f

def parse_header(d):
    h = {}
    h['magic'] = f"0x{u32(d,0):08X} ({d[0:4].hex(' ')})"
    h['version'] = u32(d, 4)
    h['f_08'] = u32(d, 8)
    h['f_0c'] = u32(d, 0xC)
    h['f_10'] = d[0x10:0x14].hex(' ')
    h['driver_module'] = cstr(d, 0x14, 32)
    h['f_20'] = d[0x20:0x30].hex(' ')
    h['f_30'] = [u32(d, 0x30+4*i) for i in range(6)]
    h['f_48'] = [u32(d, i) for i in (0x48,0x4C,0x50,0x54,0x58,0x5C,0x60,0x64)]
    h['f_68'] = u32(d, 0x68)
    h['f_78'] = u32(d, 0x78)
    h['f_7c'] = u32(d, 0x7C)
    h['f_80'] = d[0x80:0x84].hex(' ')
    h['f_e8'] = u32(d, 0xE8)
    return h

def find_ramp_lut_groups(d):
    """Find groups of 8 consecutive 256-entry double identity LUTs (1/255 at +8 of start)."""
    starts = []
    i = 0
    while True:
        i = d.find(RAMP_DOUBLE, i)
        if i < 0: break
        st = i - 8
        if st >= 0 and f64(d, st) == 0.0:
            starts.append(st)
        i += 1
    groups = []
    for st in starts:
        if groups and st - (groups[-1][-1] + 256*8) <= 16 and (st - (groups[-1][-1]+256*8)) % 12 == 0:
            groups[-1].append(st)
        else:
            groups.append([st])
    return [g for g in groups if len(g) >= 4]

def find_path_records(d):
    """Locate 260-byte stride NUL-terminated path strings. Returns list of (offset, string)."""
    pat = re.compile(rb'[A-Za-z0-9][A-Za-z0-9 _\-()./\\:]{2,}(?:\.icc|\.icm|\.mcm|\.pdv|\.wpk)\x00', re.I)
    recs = []
    for m in pat.finditer(d):
        # find record start: string start aligned so that record stride is 260
        recs.append((m.start(), m.group()[:-1].decode('latin1')))
    return recs

def parse_records(d):
    groups = find_ramp_lut_groups(d)
    recs = []
    for g in groups:
        lut_start = g[0]
        lut_end = g[-1] + 256*8
        # scan from lut_end to next 4 path strings within 1KB
        ctx = dict(lut_start=lut_start, lut_end=lut_end,
                   lut_count=len(g), lut_gap=(g[1]-g[0]-256*8) if len(g)>1 else 0)
        paths = []
        pos = lut_end
        # config struct then path group A: search strings within next 4096 bytes
        pat = re.compile(rb'[A-Za-z0-9][A-Za-z0-9 _\-()./\\:]{2,}(?:\.icc|\.icm|\.mcm|\.pdv|\.wpk)\x00', re.I)
        search_end = min(len(d), lut_end + 8192)
        for m in pat.finditer(d, lut_end, search_end):
            paths.append((m.start(), m.group()[:-1].decode('latin1')))
        ctx['paths'] = paths
        # find next lut group start
        recs.append(ctx)
    for i, r in enumerate(recs):
        r['next_lut_start'] = recs[i+1]['lut_start'] if i+1 < len(recs) else None
        r['index'] = i
    return recs

def text_block(d):
    """Extract printable NUL-terminated strings from the text/config section (first 0x9000 bytes)."""
    res = []
    pat = re.compile(rb'[\x20-\x7e]{3,}')
    for m in pat.finditer(d[:0x9000]):
        res.append(dict(off=m.start(), s=m.group().decode('latin1')))
    return res

def tail_strings(d):
    res = []
    pat = re.compile(rb'[\x20-\x7e]{3,}')
    for m in pat.finditer(d, max(0, len(d)-8000)):
        res.append(dict(off=m.start(), s=m.group().decode('latin1')))
    return res

def parse(fn):
    d = open(fn, 'rb').read()
    out = dict(file=fn, size=len(d), size_hex=f'0x{len(d):X}')
    out['header'] = parse_header(d)
    out['text_block'] = text_block(d)
    out['records'] = parse_records(d)
    out['tail'] = tail_strings(d)
    return out

def main():
    files = sys.argv[1:] or DEFAULT_PRSS
    os.makedirs(OUTDIR, exist_ok=True)
    summary = {}
    for fn in files:
        name = os.path.splitext(os.path.basename(fn))[0]
        try:
            out = parse(fn)
        except Exception as e:
            print(f'{fn}: ERROR {e}'); continue
        dest = os.path.join(OUTDIR, f'prs_dump_{name}.json')
        with open(dest, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
        print(f'{os.path.basename(fn)}: size={out["size"]} v={out["header"]["version"]} '
              f'module={out["header"]["driver_module"]} records={len(out["records"])} '
              f'text_entries={len(out["text_block"])} -> {dest}')
        for r in out['records']:
            paths = [p[1] for p in r['paths']]
            print(f'   rec{r["index"]}: lut@0x{r["lut_start"]:X} n_lut={r["lut_count"]} '
                  f'paths={paths[:4]}')
        summary[name] = dict(size=out['size'], version=out['header']['version'],
                             module=out['header']['driver_module'],
                             records=[dict(lut_start=r['lut_start'], paths=[p[1] for p in r['paths']])
                                      for r in out['records']])
    with open(os.path.join(OUTDIR, 'prs_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    print('\nsaved -> work/prs/prs_summary.json')

if __name__ == '__main__':
    main()
