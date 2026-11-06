import sys, os, struct, collections
from PIL import Image

GOLD = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
PNG  = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"

def hexdump(b, off=0, n=400):
    out=[]
    for i in range(0, min(n, len(b)), 16):
        chunk = b[off+i:off+i+16]
        hx = ' '.join('%02x'%c for c in chunk)
        asc = ''.join(chr(c) if 32<=c<127 else '.' for c in chunk)
        out.append('%08x  %-47s  %s' % (off+i, hx, asc))
    return '\n'.join(out)

d = open(GOLD,'rb').read()
print("GOLD size", len(d))
print(hexdump(d, 0, 420))

im = Image.open(PNG)
print("PNG", im.size, im.mode, im.info)
print("PNG extrema", im.getextrema() if im.mode!='RGBA' else [im.getchannel(c).getextrema() for c in range(4)])

# scan for 1b 69 occurrences
idxs = []
i = d.find(b'\x1b\x69')
while i != -1:
    idxs.append(i)
    i = d.find(b'\x1b\x69', i+2)
print("count ESC i:", len(idxs), "first", idxs[:5], "last", idxs[-5:] if idxs else None)
# print params of first few
for off in idxs[:14]:
    pr = d[off:off+10]
    color, comp, bit, nL, nH, mL, mH = pr[2], pr[3], pr[4], pr[5], pr[6], pr[7], pr[8]
    n = nL | nH<<8; m = mL | mH<<8
    print('  @%08x color=%02x comp=%02x bit=%02x n=%d m=%d  raw=%s' % (off, color, comp, bit, n, m, pr.hex(' ')))

# distinct colors / n / m
cols = collections.Counter(); ns = collections.Counter(); ms = collections.Counter()
for off in idxs:
    pr = d[off:off+10]
    cols[pr[2]] += 1; ns[pr[5]|pr[6]<<8] += 1; ms[pr[7]|pr[8]<<8] += 1
print("colors", dict(cols))
print("n distinct", len(ns), ns.most_common(10))
print("m distinct", len(ms), ms.most_common(10))

# scan ESC ( $ positions and params
i = d.find(b'\x1b\x28\x24')
pos = []
while i != -1:
    pos.append(i); i = d.find(b'\x1b\x28\x24', i+3)
print("count ESC ( $:", len(pos))
for off in pos[:6]:
    print('   @%08x %s' % (off, d[off:off+9].hex(' ')))
# distinct 4-byte params
pars = collections.Counter()
for off in pos:
    if off+9 <= len(d):
        pars[struct.unpack('<I', d[off+5:off+9])[0]] += 1
print("ESC( $ params distinct:", sorted(pars.items())[:20], "... total distinct:", len(pars))

# ESC ( v
i = d.find(b'\x1b\x28\x76')
posv=[]
while i!=-1:
    posv.append(i); i = d.find(b'\x1b\x28\x76', i+3)
print("count ESC ( v:", len(posv))
pv = collections.Counter()
for off in posv:
    pv[struct.unpack('<I', d[off+5:off+9])[0]] += 1
print("ESC(v) params:", pv.most_common(20))
print("tail 96:", d[-96:].hex(' '))
print("tail ascii:", ''.join(chr(c) if 32<=c<127 else '.' for c in d[-96:]))
