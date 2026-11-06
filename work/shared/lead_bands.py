# -*- coding: utf-8 -*-
"""Lead: band/color analysis + exact image-row offset fitting."""
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
    p = 0
    for b in blocks:
        p += b['advance']; b['pos'] = p
    return blocks

def row_bits(b, r):
    """返回 {color: [v per dot]} for block b row r"""
    out = {}
    for rec in b['records']:
        line = rec['raw'][r*rec['n']:(r+1)*rec['n']]
        bits = []
        for byte in line:
            bits += [(byte >> 6) & 3, (byte >> 4) & 3, (byte >> 2) & 3, byte & 3]
        out[rec['color']] = bits
    return out

blocks = parse_prn(PRN)
W = 4320
print("blocks", len(blocks))
# 红带/蓝带统计
red_p = range(6*25 + 644, 6*220 + 645)
blue_p = range(6*385 + 644, 6*595 + 645)
band_count = collections.defaultdict(lambda: [0, 0])
allrows = {}
for b in blocks:
    for r in range(90):
        p = b['pos'] + 8*r
        allrows[p] = (b, r)

for p, (b, r) in allrows.items():
    rb = row_bits(b, r)
    for col, bits in rb.items():
        cnt = sum(1 for v in bits if v)
        if cnt == 0: continue
        if p in red_p: band_count[col][0] += cnt
        elif p in blue_p: band_count[col][1] += cnt
print("\ncolor: ink dots in RED band / BLUE band")
for col in sorted(band_count):
    print("  %#04x : %8d / %8d" % (col, band_count[col][0], band_count[col][1]))

# 找页面行 p=1000（红带）和 p=3000（蓝带）对应的 image row 打印 x 图案
im = Image.open(PNG).convert('RGBA')
px = im.load()
Wimg, Himg = im.size
def img_row_ink(y):
    s = set()
    for x in range(Wimg):
        r, g, b, a = px[x, y]
        if a != 0 and (r, g, b) != (255, 255, 255):
            s.add(x)
    return s
def prn_row_ink(p):
    if p not in allrows: return None, None
    b, r = allrows[p]
    rb = row_bits(b, r)
    union = set()
    for col, bits in rb.items():
        for i, v in enumerate(bits):
            if v: union.add(i)
    return rb, union

for p in (1000, 3000):
    rb, union = prn_row_ink(p)
    print("\np=%d union dots=%d" % (p, len(union) if union else -1))
    for col in sorted(rb):
        bits = rb[col]
        xs = [i for i, v in enumerate(bits) if v]
        if xs:
            print("  color %02x: dots=%5d x=[%d..%d]" % (col, len(xs), xs[0], xs[-1]))
    if union:
        # 与图像行做匹配：对候选 image row 比较 x/6 集合
        best = []
        for j in range(Himg):
            s = img_row_ink(j)
            if not s: continue
            u = set(i // 6 for i in union)
            inter = len(s & u); union_n = len(s | u)
            jac = inter / union_n if union_n else 0
            if jac > 0.3:
                best.append((jac, j, len(s), len(u)))
        best.sort(reverse=True)
        print("  best matched image rows:", best[:5])
