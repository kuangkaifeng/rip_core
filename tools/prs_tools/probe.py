#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick probe of MainTop .prs files: header, strings, magic markers."""
import sys, os, re, struct, json

BIN = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin"

def hexdump(data, off, n, base=0):
    out=[]
    for i in range(0, n, 16):
        chunk = data[off+i:off+i+16]
        if not chunk: break
        hexs = ' '.join(f'{b:02X}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        out.append(f"{base+off+i:08X}  {hexs:<48}  {asc}")
    return '\n'.join(out)

def u32(d, o): return struct.unpack_from('<I', d, o)[0]
def i32(d, o): return struct.unpack_from('<i', d, o)[0]
def u16(d, o): return struct.unpack_from('<H', d, o)[0]

def probe(fn):
    d = open(fn,'rb').read()
    print('='*100)
    print(f'FILE {fn}  size={len(d)}')
    print('--- first 512 bytes ---')
    print(hexdump(d, 0, 512))
    print('--- last 256 bytes ---')
    print(hexdump(d, len(d)-256, 256, base=0))
    # ASCII strings >=4
    print('--- strings (>=4 printable), first 120 with offset ---')
    pat = re.compile(rb'[\x20-\x7e]{4,}')
    cnt=0
    for m in pat.finditer(d):
        s = m.group().decode('latin1')
        print(f'{m.start():08X} len={len(s):4d} {s[:120]}')
        cnt+=1
        if cnt>=120: print('...'); break
    # magics
    for name, sig in [('acsp',b'acsp'),('MtDummy',b'MtDummy'),('pdv',b'.pdv'),('PRS',b'PRS'),('ICC',b'ICC')]:
        offs=[m.start() for m in re.finditer(re.escape(sig), d)]
        print(f'--- marker {name}: {len(offs)} hits ---')
        print(' '.join(f'{o:X}' for o in offs[:80]))

for fn in sys.argv[1:] or [os.path.join(BIN,'A3-DTF-1390.prs')]:
    probe(fn)
