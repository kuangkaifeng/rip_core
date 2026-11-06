# -*- coding: utf-8 -*-
"""Lead: test whether overlapping blocks duplicate or partition each page row."""
import struct, collections
from PIL import Image

PRN = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"
PNG = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png"

def decode_rle(buf, j, need):
    dec = bytearray(); n = len(buf)
    while j < n and len(dec) < need:
        c = buf[j]
        if c <= 127:
            cnt = c + 1; dec += buf[j+1:j+1+cnt]; j += 1 + cnt
        else:
            cnt = 257 - c
            if j + 1 >= n: break
            dec += bytes([buf[j+1]]) * cnt; j += 2
    return bytes(dec[:need]), j

def parse_prn(path):
    buf = open(path, 'rb').read()
    blocks = []; cur = dict(advance=0, records=[]); pos = 0
    while True:
        i = buf.find(b'\x1b', pos)
        if i < 0 or i + 2 >= len(buf): break
        b1 = buf[i+1]
        if b1 == 0x69 and i + 9 <= len(buf):
            color = buf[i+2]; n = buf[i+5] | (buf[i+6] << 8); m = buf[i+7] | (buf[i+8] << 8)
            raw, j = decode_rle(buf, i+9, n*m)
            cur['records'].append(dict(color=color, n=n, m=m, raw=raw))
            pos = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i+2]; ln = buf[i+3] | (buf[i+4] << 8); data = buf[i+5:i+5+ln]
            if cmd == 0x76 and ln >= 4:
                if cur['records']: blocks.append(cur)
                cur = dict(advance=struct.unpack('<I', data[:4])[0], records=[])
            pos = i + 5 + ln
        else:
            pos = i + 1
    if cur['records']: blocks.append(cur)
    pos = 0
    for b in blocks:
        pos += b['advance']; b['pos'] = pos
    return blocks

def bits_of(raw, n):
    """2bit -> list of 4*n values"""
    out = []
    for byte in raw:
        out.append((byte >> 6) & 3); out.append((byte >> 4) & 3)
        out.append((byte >> 2) & 3); out.append(byte & 3)
    return out

blocks = parse_prn(PRN)
print("blocks", len(blocks))
# 某页面行 p 被哪些 (block,row) 覆盖
for p in (1000, 2340, 3000):
    print("\n=== page row p=%d (mod8=%d) ===" % (p, p % 8))
    for bi, b in enumerate(blocks):
        if (p - b['pos']) % 8 != 0: continue
        r = (p - b['pos']) // 8
        if not (0 <= r < 90): continue
        sig = []
        for rec in b['records']:
            line = rec['raw'][r*rec['n']:(r+1)*rec['n']]
            ink = sum(1 for byte in line if byte)
            xr = None
            for byi, byte in enumerate(line):
                if byte:
                    xr = (byi*4, byi*4+3) if xr is None else (xr[0], byi*4+3)
            sig.append("%02x:ink=%4d x=%s" % (rec['color'], ink, xr))
        print("  b%02d r=%2d  %s" % (bi, r, " | ".join(sig)))
    # 用该行所有 (block,row) 的并集/交集统计
    per_color_masks = collections.defaultdict(lambda: [0]*600)
    nblk = 0
    for bi, b in enumerate(blocks):
        if (p - b['pos']) % 8 != 0: continue
        r = (p - b['pos']) // 8
        if not (0 <= r < 90): continue
        nblk += 1
        for rec in b['records']:
            bits = bits_of(rec['raw'][r*rec['n']:(r+1)*rec['n']], rec['n'])
            for i, v in enumerate(bits):
                if v:
                    per_color_masks[rec['color']][i] += 1
    print("  blocks covering p=%d: %d" % (p, nblk))
    for col, arr in per_color_masks.items():
        vals = collections.Counter(arr)
        print("  color %02x: dot-count-distribution %s" % (col, dict(list(vals.items())[:6])))
