#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""parse_hssf.py -- parser / generator / validator for 北印 BetterPrinter HSSF PRN.

Target: H13 (XP600 head) board-machine PRN produced by MainTop RIP
(KaartrekenaarRip.json + H13 XP600.prs) and consumed by BetterPrinter.dll
(bpPrintSendTask -> BP_PRINT_TASK -> board).

Verified facts (see docs/prn_board.md for evidence):
  * 48-byte little-endian header (12 x UINT32).  Layout identical to
    ImageFormat.h::PRN_IMAGE_INFO (HSSF, signature 0x5555).
  * nPaperWidth is a float32 physical media width in *metres* stored in the
    UINT slot: nPaperWidth = float32(nWidth / nXDPI * 0.0254).
  * Data area starts at offset 48, row-interleaved:
        for y in 0..H-1:
            for c in 0..C-1:
                row(c,y) = BPL bytes
  * Each row is BPL bytes.  **MainTop RIP aligns BPL to 8 bytes**
    (BPL = align8(ceil(W*dotBits/8))); proof: oracle
    reference/prn_samples/exp_h13xp600_h13_scale50.prn has W=300, 2bit
    -> ceil=75 -> align4=76 but file BPL=80 (=align8).  Vendor TestFile
    (北印自己做测试图时) uses 4-byte alignment instead
    (720x720_4C+WO.prn: W=5670 -> 1420=align4, align8 would be 1424).
    Both are tolerated by readers because BPL comes from the header;
    we mimic MainTop -> use align8.
  * Pixel packing is MSB first:
        dotbit=2 : value of pixel x -> bits (6-2*(x%4)) of byte x//4
        dotbit=1 : value of pixel x -> bit  (7-(x%8))  of byte x//8
  * H13 (XP600) channel/plane order is **K, C, M, Y, W1** (C=5), verified
    with single-colour oracle samples (h13xp600_flat_*.prn): flat_k fills
    plane0, flat_c plane1, flat_m plane2, flat_y plane3; W1 full fills
    plane4.  Vendor TestFile are the same order (4C+WO adds two planes).
  * dotBits: MainTop writes nReserved[0]=0 for H13 samples; the reader
    infers it from BPL/W exactly like 北印 demo GetPrnFileInfo does.
    Vendor TestFile samples set nReserved[0]=bits, [1]=pass, [2]=1.
  * No pass/chunk/page headers, no compression: file size must be exactly
    48 + H*C*BPL.

Usage:
    python parse_hssf.py info  <file.prn>
    python parse_hssf.py planes <file.prn> --out dir [--layout line|plane] [--scale N]
    python parse_hssf.py check <file.prn> [<file.prn> ...]
    python parse_hssf.py make  <spec.json>        # build a minimal valid PRN

Pure stdlib (no PIL/numpy).
"""
import argparse
import json
import os
import struct
import sys
import zlib

HEADER_SIZE = 48
HSSF_SIG = 0x5555
YCDZ_SIG = 0x7A646379
BYHX_SIG = 0x58485942
AT_SIG = 0x4D435441

HEADER_FIELDS = ['nSignature', 'nXDPI', 'nYDPI', 'nBytesPerLine', 'nHeight',
                 'nWidth', 'nPaperWidthRaw', 'nColorPlane',
                 'nReserved0', 'nReserved1', 'nReserved2', 'nReserved3']

# nReserved contract used by 北印 TestFile samples:
#   [0]=dot bits, [1]=pass count, [2]=1 (unknown, "存储行数"?), [3]=0
# MainTop-generated H13 samples leave all four 0 and readers infer dot bits.


def align4(n):
    return (n + 3) & ~3


def align8(n):
    return (n + 7) & ~7


def expected_bpl(width, dotbit, align=8):
    """MainTop uses align=8 (verified); vendor TestFile uses align=4."""
    raw = (width * dotbit + 7) // 8
    return align4(raw) if align == 4 else align8(raw)


def infer_dotbit(bpl, width):
    """Exactly the fallback logic of 北印 demo GetPrnFileInfo / rip-studio readPrnInfo."""
    if width <= 0:
        return 0
    if bpl <= width // 8 + 32:
        return 1
    if bpl <= width // 4 + 32:
        return 2
    if bpl <= width // 2 + 32:
        return 4
    if bpl <= width + 32:
        return 8
    if bpl <= width * 2 + 32:
        return 16
    return 0


class HssfPrn(object):
    def __init__(self, path):
        self.path = path
        self.raw = open(path, 'rb').read()
        if len(self.raw) < HEADER_SIZE:
            raise ValueError('file too small for HSSF header')
        vals = struct.unpack('<12I', self.raw[:HEADER_SIZE])
        self.h = dict(zip(HEADER_FIELDS, vals))
        self.signature = self.h['nSignature']
        self.paper_width_m = struct.unpack('<f', struct.pack('<I', self.h['nPaperWidthRaw']))[0]
        self.width = self.h['nWidth']
        self.height = self.h['nHeight']
        self.planes = self.h['nColorPlane']
        self.bpl = self.h['nBytesPerLine']
        self.xdpi = self.h['nXDPI']
        self.ydpi = self.h['nYDPI']
        self.reserved = [self.h['nReserved0'], self.h['nReserved1'],
                         self.h['nReserved2'], self.h['nReserved3']]
        if self.signature != HSSF_SIG:
            raise ValueError('not HSSF 0x5555: 0x%08X' % self.signature)
        r0 = self.reserved[0]
        self.dotbit = r0 if r0 in (1, 2, 4, 8, 16) else infer_dotbit(self.bpl, self.width)
        self.datasize = len(self.raw) - HEADER_SIZE
        self.expected = (self.width, self.height, self.planes, self.bpl, self.dotbit)
        self.bytes_per_row_all_planes = self.bpl * self.planes
        self.expected_datasize = self.height * self.planes * self.bpl

    # -- basics -----------------------------------------------------------
    def describe(self):
        d = {}
        d.update(self.h)
        d['paperWidthFloat_m'] = self.paper_width_m
        d['dotBits_inferred'] = self.dotbit
        d['reserved_contract'] = ('vendor TestFile style (bits,pass,1,0)'
                                  if self.reserved[0] in (1, 2, 4, 8, 16)
                                  else 'MainTop style zeros (reader infers bits)')
        d['dataBytes_actual'] = self.datasize
        d['dataBytes_HxCxBPL'] = self.expected_datasize
        d['size_ok'] = self.datasize == self.expected_datasize
        d['pixels_per_byte'] = {1: 8, 2: 4, 4: 2, 8: 1}.get(self.dotbit)
        d['physical_mm_x'] = self.width / self.xdpi * 25.4 if self.xdpi else None
        d['physical_mm_y'] = self.height / self.ydpi * 25.4 if self.ydpi else None
        return d

    # -- decode -----------------------------------------------------------
    def plane_rows(self, plane, layout='line'):
        """Yield H rows of dot values (0..(2^dotbit-1)) for one plane."""
        C, W, H, BPL, db = self.planes, self.width, self.height, self.bpl, self.dotbit
        raw = self.raw
        if layout == 'line':
            base = HEADER_SIZE + plane * BPL
            stride = C * BPL
        elif layout == 'plane':
            base = HEADER_SIZE + plane * H * BPL
            stride = BPL
        else:
            raise ValueError(layout)
        for y in range(H):
            off = base + y * stride
            row = raw[off:off + BPL]
            yield unpack_row(row, W, db)

    def plane_bytes(self, plane, maxrow=None):
        C, BPL = self.planes, self.bpl
        base = HEADER_SIZE + plane * BPL
        stride = C * BPL
        n = self.height if maxrow is None else min(maxrow, self.height)
        out = bytearray()
        for y in range(n):
            off = base + y * stride
            out += self.raw[off:off + BPL]
        return bytes(out)

    def row(self, y):
        """Return the raw bytes of the complete row record (all planes)."""
        off = HEADER_SIZE + y * self.bpl * self.planes
        return self.raw[off:off + self.bpl * self.planes]


def unpack_row(buf, width, dotbit):
    """MSB-first unpacking. Returns bytearray of dot values."""
    out = bytearray(width)
    if dotbit == 2:
        for x in range(width):
            out[x] = (buf[x >> 2] >> (6 - 2 * (x & 3))) & 3
    elif dotbit == 1:
        for x in range(width):
            out[x] = (buf[x >> 3] >> (7 - (x & 7))) & 1
    elif dotbit == 4:
        for x in range(width):
            out[x] = (buf[x >> 1] >> (4 - 4 * (x & 1))) & 0xF
    elif dotbit == 8:
        out[x] = buf[x]
    else:
        raise ValueError('dotbit %d unsupported' % dotbit)
    return out


def pack_row(vals, width, bpl, dotbit):
    """Inverse of unpack_row: MSB-first packing, pad row to bpl bytes."""
    out = bytearray(bpl)
    if dotbit == 2:
        for x in range(width):
            out[x >> 2] |= (vals[x] & 3) << (6 - 2 * (x & 3))
    elif dotbit == 1:
        for x in range(width):
            out[x >> 3] |= (vals[x] & 1) << (7 - (x & 7))
    elif dotbit == 8:
        for x in range(width):
            out[x] = vals[x] & 0xFF
    else:
        raise ValueError('dotbit %d unsupported' % dotbit)
    return bytes(out)


# ------------------------------------------------------------------ preview
def png_write(path, w, h, rgb):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]

    def chunk(typ, data):
        c = struct.pack('>I', len(data)) + typ + data
        return c + struct.pack('>I', zlib.crc32(typ + data) & 0xFFFFFFFF)
    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(bytes(raw), 6))
    out += chunk(b'IEND', b'')
    open(path, 'wb').write(out)


def render_plane_png(prn, plane, path, scale=8, layout='line'):
    """Max-pool downscale of one plane -> grayscale PNG."""
    W, H = prn.width, prn.height
    step = max(1, scale)
    ow, oh = (W + step - 1) // step, (H + step - 1) // step
    rgb = bytearray(ow * oh * 3)
    vmax = (1 << prn.dotbit) - 1
    for oy, row in enumerate(prn.plane_rows(plane, layout)):
        oy2 = oy // step
        if oy2 >= oh:
            break
        base = oy2 * ow
        for ox in range(ow):
            lo = ox * step
            hi = min(W, lo + step)
            m = 0
            for x in range(lo, hi):
                v = row[x]
                if v > m:
                    m = v
            g = int(255 * m / vmax) if vmax else 0
            o = (base + ox) * 3
            rgb[o] = rgb[o + 1] = rgb[o + 2] = g
    png_write(path, ow, oh, bytes(rgb))


def render_composite_png(prn, path, scale=8, layout='line', plane_map=None):
    """Render planes as an RGB composite (naive CMYK -> RGB, W ignored).

    plane_map: list such that plane_map[i] = 'C'|'M'|'Y'|'K'|'W'|None.
    Default: K,C,M,Y,W for 5-plane device like H13 (documented hypothesis).
    """
    W, H = prn.width, prn.height
    step = max(1, scale)
    ow, oh = (W + step - 1) // step, (H + step - 1) // step
    # decode planes into downsampled 0..255 ink amount arrays
    ink = {}
    vmax = (1 << prn.dotbit) - 1
    for p in range(prn.planes):
        arr = bytearray(ow * oh)
        for oy, row in enumerate(prn.plane_rows(p, layout)):
            oy2 = oy // step
            if oy2 >= oh:
                break
            for ox in range(ow):
                lo = ox * step
                hi = min(W, lo + step)
                m = 0
                for x in range(lo, hi):
                    v = row[x]
                    if v > m:
                        m = v
                arr[oy2 * ow + ox] = int(255 * m / vmax)
        ink[p] = arr
    if plane_map is None:
        # H13 verified: K,C,M,Y,W1 (5 planes); vendor 4C+WO has 6 planes
        if prn.planes == 5:
            plane_map = ['K', 'C', 'M', 'Y', 'W']
        elif prn.planes == 6:
            plane_map = ['K', 'C', 'M', 'Y', 'W', 'O']
        else:
            plane_map = ['K', 'C', 'M', 'Y', 'W', 'O'] + [None] * (prn.planes - 6)
    rgb = bytearray(ow * oh * 3)
    for i in range(ow * oh):
        C = M = Y = K = 0
        for p, role in enumerate(plane_map):
            if role is None:
                continue
            v = ink[p][i]
            if role == 'C':
                C = v
            elif role == 'M':
                M = v
            elif role == 'Y':
                Y = v
            elif role == 'K':
                K = v
        # simple subtractive composite
        r = 255 - C - K
        g = 255 - M - K
        b = 255 - Y - K
        rgb[i * 3] = max(0, min(255, r))
        rgb[i * 3 + 1] = max(0, min(255, g))
        rgb[i * 3 + 2] = max(0, min(255, b))
    png_write(path, ow, oh, bytes(rgb))


# ------------------------------------------------------------------- make
def make_minimal_prn(out_path, width=8, height=4, xdpi=720, ydpi=1080,
                     planes=5, dotbit=2, fill=None, reserved=None,
                     align=8, paper_width=None):
    """Create a minimal HSSF PRN.

    fill: list of per-plane constant dot values (len == planes), e.g. [0,0,0,0,3]
          for "white plane full canvas".
    reserved: [r0,r1,r2,r3]; default mimics vendor TestFile: [dotbit, pass=1, 1, 0]
    align: bytesPerLine alignment; MainTop=8 (default), vendor TestFile=4.
    paper_width: override nPaperWidth float metres; default W/xDPI*0.0254 (MainTop rule).
    """
    if fill is None:
        fill = [0] * planes
    if reserved is None:
        reserved = [dotbit, 1, 1, 0]
    bpl = expected_bpl(width, dotbit, align)
    paper_m = paper_width if paper_width is not None else width / float(xdpi) * 0.0254
    hdr = struct.pack('<12I', HSSF_SIG, xdpi, ydpi, bpl, height, width,
                      struct.unpack('<I', struct.pack('<f', paper_m))[0],
                      planes, *reserved)
    data = bytearray()
    for y in range(height):
        for c in range(planes):
            vals = bytearray([fill[c] & ((1 << dotbit) - 1)] * width)
            data += pack_row(vals, width, bpl, dotbit)
    open(out_path, 'wb').write(hdr + bytes(data))
    return bpl, HEADER_SIZE + len(data)


# ------------------------------------------------------------------ checks
def check_file(path):
    try:
        prn = HssfPrn(path)
    except Exception as e:
        print('%-70s FAIL: %s' % (os.path.basename(path), e))
        return False
    d = prn.describe()
    ok = d['size_ok']
    print('%-70s sig=0x%04X %dx%d dpi=%dx%d C=%d bpl=%d dot=%d data=%d/%d %s'
          % (os.path.basename(path), prn.signature, prn.width, prn.height,
             prn.xdpi, prn.ydpi, prn.planes, prn.bpl, prn.dotbit,
             prn.datasize, prn.expected_datasize, 'OK' if ok else 'SIZE-MISMATCH'))
    return ok


def selftest_file(path):
    """Stronger invariant checks used to validate a HSSF writer / corpus."""
    try:
        prn = HssfPrn(path)
    except ValueError as e:
        sig = struct.unpack('<I', open(path, 'rb').read(4))[0] if os.path.getsize(path) >= 4 else 0
        known = {YCDZ_SIG: 'YCDZ', BYHX_SIG: 'BYHX', AT_SIG: 'AT',
                 0x1B000000: 'ESC/P2', 0xFE784D42: 'BMP(SaveInk)', 0x74667966: 'unknown "fyft"'}
        print('%-60s SKIP  not HSSF: 0x%08X (%s)'
              % (os.path.basename(path), sig, known.get(sig, '?')))
        return None
    problems = []
    # 1) bpl formula (accept MainTop align8 or vendor TestFile align4)
    a8 = expected_bpl(prn.width, prn.dotbit, 8)
    a4 = expected_bpl(prn.width, prn.dotbit, 4)
    if prn.bpl == a8:
        align_tag = 'align8(MainTop)'
    elif prn.bpl == a4:
        align_tag = 'align4(vendor TestFile)'
    else:
        align_tag = 'BAD'
        problems.append('bpl=%d not align4(%d) nor align8(%d)' % (prn.bpl, a4, a8))
    # 2) exact data size
    if prn.datasize != prn.expected_datasize:
        problems.append('size=%d != 48+H*C*bpl=%d' % (prn.datasize + 48, prn.expected_datasize + 48))
    # 3) paper width (float metres) ~= W/xDPI*0.0254
    if prn.xdpi:
        want = prn.width / prn.xdpi * 0.0254
        if abs(prn.paper_width_m - want) > max(1e-6, want * 1e-4):
            problems.append('paperWidth=%.9f != W/xDPI*0.0254=%.9f' % (prn.paper_width_m, want))
    # 4) reserved sanity
    r0 = prn.reserved[0]
    if r0 not in (0, 1, 2, 4, 8, 16):
        problems.append('reserved[0]=%d unexpected' % r0)
    if problems:
        print('%-60s FAIL  %s' % (os.path.basename(path), '; '.join(problems)))
        return False
    print('%-60s PASS  sig=0x%04X %dx%d dpi=%dx%d C=%d bpl=%d %s dot=%d pw=%.8f r=%s'
          % (os.path.basename(path), prn.signature, prn.width, prn.height,
             prn.xdpi, prn.ydpi, prn.planes, prn.bpl, align_tag, prn.dotbit,
             prn.paper_width_m, prn.reserved))
    return True


# ------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description='HSSF (0x5555) PRN parser/validator')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_info = sub.add_parser('info')
    p_info.add_argument('file')

    p_pl = sub.add_parser('planes')
    p_pl.add_argument('file')
    p_pl.add_argument('--out', default='.')
    p_pl.add_argument('--layout', default='line', choices=['line', 'plane'])
    p_pl.add_argument('--scale', type=int, default=8,
                      help='downscale step in source pixels (default 8)')

    p_chk = sub.add_parser('check')
    p_chk.add_argument('files', nargs='+')

    p_st = sub.add_parser('selftest',
                          help='validate HSSF header invariants (bpl/size/paperWidth/reserved)')
    p_st.add_argument('files', nargs='+')

    p_mk = sub.add_parser('make')
    p_mk.add_argument('--out', default='minimal.prn')
    p_mk.add_argument('--width', type=int, default=8)
    p_mk.add_argument('--height', type=int, default=4)
    p_mk.add_argument('--xdpi', type=int, default=720)
    p_mk.add_argument('--ydpi', type=int, default=1080)
    p_mk.add_argument('--planes', type=int, default=5)
    p_mk.add_argument('--dotbit', type=int, default=2)
    p_mk.add_argument('--fill', default=None,
                      help='comma separated per-plane constant values, e.g. 0,0,0,0,3')
    p_mk.add_argument('--reserved', default=None, help='r0,r1,r2,r3')
    p_mk.add_argument('--align', type=int, default=8, choices=[4, 8],
                      help='bytesPerLine alignment: MainTop=8 (default), vendor TestFile=4')

    args = ap.parse_args(argv)
    if args.cmd == 'info':
        prn = HssfPrn(args.file)
        print(json.dumps(prn.describe(), indent=2))
    elif args.cmd == 'planes':
        prn = HssfPrn(args.file)
        os.makedirs(args.out, exist_ok=True)
        stem = os.path.splitext(os.path.basename(args.file))[0]
        for p in range(prn.planes):
            out = os.path.join(args.out, '%s_p%d.png' % (stem, p))
            render_plane_png(prn, p, out, scale=args.scale, layout=args.layout)
            print(out)
        comp = os.path.join(args.out, '%s_composite.png' % stem)
        render_composite_png(prn, comp, scale=args.scale, layout=args.layout)
        print(comp)
    elif args.cmd == 'check':
        allok = True
        for f in args.files:
            allok = check_file(f) and allok
        return 0 if allok else 1
    elif args.cmd == 'selftest':
        npass = nfail = nskip = 0
        for f in args.files:
            r = selftest_file(f)
            if r is None:
                nskip += 1
            elif r:
                npass += 1
            else:
                nfail += 1
        print('--- selftest: PASS=%d FAIL=%d SKIP=%d' % (npass, nfail, nskip))
        return 0 if nfail == 0 else 1
    elif args.cmd == 'make':
        fill = [int(x) for x in args.fill.split(',')] if args.fill else None
        res = [int(x) for x in args.reserved.split(',')] if args.reserved else None
        bpl, total = make_minimal_prn(args.out, args.width, args.height,
                                      args.xdpi, args.ydpi, args.planes,
                                      args.dotbit, fill, res, args.align)
        print('wrote %s: bpl=%d size=%d' % (args.out, bpl, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
