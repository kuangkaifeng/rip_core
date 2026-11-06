#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe HSSF PRN data layout against a known image source.

Reads:
  - HSSF 0x5555 PRN (from MainTop RIP, H13 XP600.prs modeId=1)  -> 1788919812455.prn
  - source PNG (the image that was RIPed)                       -> 1788919812307.png
Writes downscaled 24-bit BMP previews for both candidate layouts
(plane-major vs line-interleaved) so they can be inspected/compared.

Pure stdlib only (no PIL/numpy available).
"""
import struct
import zlib
import sys
import os

# ---------------------------------------------------------------- PNG decode
def png_read(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'not png'
    pos = 8
    w = h = bd = ct = inter = None
    idat = b''
    while pos < len(d):
        ln = struct.unpack('>I', d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        data = d[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            w, h, bd, ct, comp, filt, inter = struct.unpack('>IIBBBBB', data)
        elif typ == b'IDAT':
            idat += data
        elif typ == b'IEND':
            break
        pos += 12 + ln
    assert bd == 8 and ct in (2, 6) and inter == 0, (bd, ct, inter)
    nch = 4 if ct == 6 else 3
    raw = zlib.decompress(idat)
    stride = w * nch
    out = bytearray(w * h * nch)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 0:
            pass
        elif ft == 1:  # Sub
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 0xFF
        elif ft == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:  # Average
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:  # Paeth
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        else:
            raise ValueError('filter %d' % ft)
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, nch, bytes(out)

# ---------------------------------------------------------------- BMP write
def png_write(path, w, h, rgb):
    """Minimal RGB PNG writer (filter 0)."""
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

def bmp_write24(path, w, h, rgb):
    """rgb: bytes len w*h*3, top-down rows."""
    rowsz = (w * 3 + 3) & ~3
    data = bytearray()
    for y in range(h - 1, -1, -1):
        row = rgb[y * w * 3:(y + 1) * w * 3]
        data += row + b'\x00' * (rowsz - w * 3)
    hdr = struct.pack('<2sIHHI', b'BM', 54 + len(data), 0, 0, 54)
    dib = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, len(data), 2835, 2835, 0, 0)
    open(path, 'wb').write(hdr + dib + bytes(data))

def bmp_read(path):
    d = open(path, 'rb').read()
    off = struct.unpack('<I', d[10:14])[0]
    w, h = struct.unpack('<ii', d[18:26])
    bpp = struct.unpack('<H', d[28:30])[0]
    assert bpp == 32, bpp
    stride = w * 4
    px = bytearray(w * abs(h) * 4)
    for y in range(abs(h)):
        src = off + (abs(h) - 1 - y if h > 0 else y) * stride
        px[y * stride:(y + 1) * stride] = d[src:src + stride]
    return w, abs(h), px

# ---------------------------------------------------------------- PRN parse
HSSF_FIELDS = ['nSignature', 'nXDPI', 'nYDPI', 'nBytesPerLine', 'nHeight',
               'nWidth', 'nPaperWidthF', 'nColorPlane', 'r0', 'r1', 'r2', 'r3']

def parse_prn(path):
    d = open(path, 'rb').read()
    vals = struct.unpack('<12I', d[:48])
    h = dict(zip(HSSF_FIELDS, vals))
    h['nPaperWidthF'] = struct.unpack('<f', struct.pack('<I', vals[6]))[0]
    h['filesize'] = len(d)
    h['datasize'] = len(d) - 48
    h['dotbit_inferred'] = infer_dotbit(h['nBytesPerLine'], h['nWidth'])
    h['PixelsPerRow'] = {1: 8, 2: 4, 4: 2, 8: 1}.get(h['dotbit_inferred'])
    h['_data'] = d
    return h

def infer_dotbit(bpl, width):
    """Same heuristic as rip-studio readPrnInfo (demo GetPrnFileInfo)."""
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

def unpack_row(buf, width, dotbit):
    """MSB-first packing (assumption to be verified)."""
    out = bytearray(width)
    if dotbit == 2:
        for x in range(width):
            b = buf[x >> 2]
            out[x] = (b >> (6 - 2 * (x & 3))) & 3
    elif dotbit == 1:
        for x in range(width):
            out[x] = (buf[x >> 3] >> (7 - (x & 7))) & 1
    else:
        raise ValueError('dotbit %d not handled' % dotbit)
    return out

def decode(prn, layout, plane):
    """Return list of rows (bytes) of dot values for one plane."""
    h = prn
    C, W, H, BPL, db = h['nColorPlane'], h['nWidth'], h['nHeight'], h['nBytesPerLine'], h['dotbit_inferred']
    data = h['_data']
    rows = []
    if layout == 'plane':       # plane-major: plane block = H*BPL
        base = 48 + plane * H * BPL
        for y in range(H):
            off = base + y * BPL
            rows.append(unpack_row(data[off:off + BPL], W, db))
    elif layout == 'line':      # line-interleaved: row = C*BPL, then plane
        for y in range(H):
            off = 48 + y * C * BPL + plane * BPL
            rows.append(unpack_row(data[off:off + BPL], W, db))
    else:
        raise ValueError(layout)
    return rows

def downsample_bmp(path, rows, maxdim=420):
    H = len(rows)
    W = len(rows[0]) if H else 0
    step = max(1, (max(W, H) + maxdim - 1) // maxdim)
    ow, oh = (W + step - 1) // step, (H + step - 1) // step
    rgb = bytearray(ow * oh * 3)
    gmax = 0
    for r in rows:
        m = max(r) if r else 0
        if m > gmax:
            gmax = m
    vmax = 3 if gmax > 1 else 1
    for oy in range(oh):
        for ox in range(ow):
            m = 0
            for yy in range(oy * step, min(H, oy * step + step)):
                r = rows[yy]
                for xx in range(ox * step, min(W, ox * step + step)):
                    if r[xx] > m:
                        m = r[xx]
            v = int(255 * m / (3 if vmax == 3 else 1))
            o = (oy * ow + ox) * 3
            rgb[o] = rgb[o + 1] = rgb[o + 2] = v
    png_write(path, ow, oh, bytes(rgb))
    return ow, oh

def coverage(rows):
    tot = 0
    nz = 0
    hist = [0, 0, 0, 0]
    for r in rows:
        for v in r:
            hist[v & 3] += 1
            tot += 1
            if v:
                nz += 1
    return nz / max(1, tot), hist

if __name__ == '__main__':
    prn_path = sys.argv[1] if len(sys.argv) > 1 else \
        r'D:\Code\kkf\ripstudio\bin\bin\temp\data\1788919812455.prn'
    outdir = sys.argv[2] if len(sys.argv) > 2 else \
        r'D:\work\RIP核心分析\work\board\out'
    os.makedirs(outdir, exist_ok=True)
    prn = parse_prn(prn_path)
    print('PRN:', {k: v for k, v in prn.items() if not k.startswith('_')})
    C = prn['nColorPlane']
    for layout in ('plane', 'line'):
        for p in range(C):
            rows = decode(prn, layout, p)
            cov, hist = coverage(rows)
            ow, oh = downsample_bmp(os.path.join(outdir, 'p%d_%s.png' % (p, layout)), rows)
            print('%s plane %d: cov=%.4f hist=%s -> %dx%d' % (layout, p, cov, hist, ow, oh))
    # source PNG -> bmp for visual comparison
    if len(sys.argv) > 3:
        w, h, nch, px = png_read(sys.argv[3])
        rgb = bytearray(w * h * 3)
        for i in range(w * h):
            rgb[i * 3:i * 3 + 3] = px[i * nch:i * nch + 3]
        png_write(os.path.join(outdir, 'source.png'), w, h, bytes(rgb))
        print('source png', w, h, 'nch', nch)
