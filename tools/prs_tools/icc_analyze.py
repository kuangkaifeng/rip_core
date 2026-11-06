#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ICC profile header/tag analyzer (pure python, no deps) + optional Pillow ImageCms info."""
import struct, sys, os, json, hashlib

def parse_header(d):
    h = {}
    h['size'] = struct.unpack_from('>I', d, 0)[0]
    h['cmm'] = d[4:8].decode('latin1')
    h['version_major'] = d[8]
    h['version_minor'] = d[9]
    h['version'] = f'{d[8]}.{d[9]}.{d[10]}.{d[11]}'
    h['class'] = d[12:16].decode('latin1')
    h['colorspace'] = d[16:20].decode('latin1')
    h['pcs'] = d[20:24].decode('latin1')
    h['datetime'] = struct.unpack_from('>6H', d, 24)
    h['platform'] = d[40:44].decode('latin1')
    h['flags'] = struct.unpack_from('>I', d, 44)[0]
    h['manufacturer'] = d[48:52].decode('latin1')
    h['model'] = d[52:56].decode('latin1')
    h['attributes'] = struct.unpack_from('>Q', d, 56)[0]
    h['intent'] = struct.unpack_from('>I', d, 64)[0]
    h['illuminant'] = struct.unpack_from('>3i', d, 68)
    h['creator'] = d[80:84].decode('latin1')
    h['id'] = d[84:100].hex()
    return h

def parse_tags(d):
    n = struct.unpack_from('>I', d, 128)[0]
    tags = []
    for i in range(n):
        o = 132 + i*12
        if o+12 > len(d): break
        sig = d[o:o+4].decode('latin1')
        off = struct.unpack_from('>I', d, o+4)[0]
        size = struct.unpack_from('>I', d, o+8)[0]
        tags.append(dict(sig=sig, off=off, size=size, type_=d[off:off+4].decode('latin1') if off+4 <= len(d) else '?'))
    return tags

def parse_mft2(d, off):
    """Parse lut16Type/lut8Type (mft2/mft1). Return dict."""
    t = d[off:off+4].decode('latin1')
    if t == 'mft2':
        n_in, n_out, n_grid, pad = d[off+8], d[off+9], d[off+10], d[off+11]
        m = struct.unpack_from('>3i', d, off+12)  # 3x3 matrix (s15Fixed16)
        n_entries = struct.unpack_from('>H', d, off+48)[0]
        p = off + 50
        in_tab = [[struct.unpack_from('>H', d, p + (i*n_in + c)*2)[0] for i in range(n_entries)] for c in range(n_in)]
        p += n_entries * n_in * 2
        out_tab = [[struct.unpack_from('>H', d, p + (i*n_out + c)*2)[0] for i in range(n_entries)] for c in range(n_out)]
        p += n_entries * n_out * 2
        n_clut = n_grid ** n_in
        clut = []
        for i in range(n_clut):
            row = [struct.unpack_from('>H', d, p + (i*n_out + c)*2)[0] for c in range(n_out)]
            clut.append(row)
        return dict(type=t, n_in=n_in, n_out=n_out, n_grid=n_grid, matrix=[x/65536.0 for x in m],
                    n_entries=n_entries, in_tab=in_tab, out_tab=out_tab, clut=clut)
    elif t == 'mft1':
        n_in, n_out, n_grid, pad = d[off+8], d[off+9], d[off+10], d[off+11]
        p = off + 48
        n_clut = n_grid ** n_in
        clut = [list(d[p + i*n_out: p + (i+1)*n_out]) for i in range(n_clut)]
        p += n_clut * n_out
        in_tab = [list(d[p + c*256: p + (c+1)*256]) for c in range(n_in)]
        p += n_in*256
        out_tab = [list(d[p + c*256: p + (c+1)*256]) for c in range(n_out)]
        return dict(type=t, n_in=n_in, n_out=n_out, n_grid=n_grid, clut=clut, in_tab=in_tab, out_tab=out_tab)
    return None

def parse_mAB(d, off):
    t = d[off:off+4].decode('latin1')
    if t not in ('mAB ', 'mBA '):
        return None
    n_in, n_out = d[off+8], d[off+9]
    hdr = dict(type=t, n_in=n_in, n_out=n_out)
    for i, name in enumerate(['B', 'matrix', 'M', 'CLUT', 'A']):
        poff = off + 12 + i*4
        toff = struct.unpack_from('>I', d, poff)[0]
        hdr[name] = None
        if toff:
            hdr[name] = dict(off=off+toff, type_=d[off+toff:off+toff+4].decode('latin1'))
    return hdr

def analyze(fn):
    d = open(fn, 'rb').read()
    if d[36:40] != b'acsp':
        print(f'{fn}: NOT ICC (no acsp) head={d[:16].hex(" ")}')
        return None
    h = parse_header(d)
    tags = parse_tags(d)
    print('='*100)
    print(f'{fn}  ({len(d)} bytes)')
    print(json.dumps(h, indent=1))
    print(f'tags ({len(tags)}):')
    for t in tags:
        print(f"  {t['sig']} type={t['type_']:<4} off=0x{t['off']:06X} size={t['size']}")
    return d, h, tags

def main():
    for fn in sys.argv[1:]:
        analyze(fn)

if __name__ == '__main__':
    main()
