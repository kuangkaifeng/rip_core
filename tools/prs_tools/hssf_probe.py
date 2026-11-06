#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Minimal HSSF (0x5555) PRN decoder for MainTop->北印 board PRNs.
Header per northPrintSDK/include/ImageFormat.h _PRN_IMAGE_INFO (12 x UINT32 = 48 bytes).
"""
import sys, struct, os

def parse(fn):
    d = open(fn, 'rb').read()
    sig, xdpi, ydpi, bpl, h, w, paperw, planes = struct.unpack_from('<8I', d, 0)
    res = struct.unpack_from('<4I', d, 32)
    print(f'{os.path.basename(fn)}: size={len(d)} sig=0x{sig:04X} xdpi={xdpi} ydpi={ydpi} bpl={bpl} h={h} w={w} paperW={paperw} planes={planes} reserved={res}')
    print(f'  head48: {d[:48].hex(" ")}')
    print(f'  head96: {d[:96].hex(" ")}')
    # guess data volume
    for bpc in (1, 2, 4, 8):
        need = bpl*h*planes*bpc//8
        if need + 48 <= len(d):
            print(f'  bpc={bpc}: need={need} (+48={need+48}) file={len(d)} rest={len(d)-48-need}')
    return d

if __name__ == '__main__':
    for fn in sys.argv[1:]:
        parse(fn)
