# -*- coding: utf-8 -*-
"""Lead: validate page mapping p = pos + 8r, and image mapping p = P0 + 6*j."""
import struct, collections, random
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
    p = 0
    for b in blocks:
        p += b['advance']; b['pos'] = p
    return blocks

def row_union(b, r):
    s = set()
    for rec in b['records']:
        line = rec['raw'][r*rec['n']:(r+1)*rec['n']]
        bi = 0
        for byte in line:
            if byte:
                for k in range(4):
                    if byte & (0xC0 >> (2*k)):
                        s.add(bi*4+k)
            bi += 1
    return s

blocks = parse_prn(PRN)
im = Image.open(PNG).convert('RGBA'); px = im.load(); W, H = im.size
def img_ink_cols(y):
    return set(x for x in range(W) if (lambda p: p[3] != 0 and (p[0], p[1], p[2]) != (255, 255, 255))(px[x, y]))

# 预计算图像行 mask
imgcols = [img_ink_cols(y) for y in range(H)]

def jac(a, b):
    if not a and not b: return 1.0
    return len(a & b) / len(a | b)

results = []
for spacing in (8, 16):
    for offset in range(638, 660):
        scores = []
        random.seed(1)
        samples = []
        for b in blocks:
            for r in (5, 25, 45, 65, 85):
                samples.append((b, r))
        for b, r in samples:
            p = b['pos'] + spacing * r
            img_row = round((p - offset) / 6.0)
            if not (0 <= img_row < H):
                scores.append(0.0); continue
            u = row_union(b, r)
            u_scaled = set(i // 6 for i in u)
            scores.append(jac(u_scaled, imgcols[img_row]))
        results.append((sum(scores)/len(scores), spacing, offset))
results.sort(reverse=True)
print("top candidates (mean jaccard, spacing, offset):")
for t in results[:8]:
    print("  %.4f spacing=%d offset=%d" % t)
