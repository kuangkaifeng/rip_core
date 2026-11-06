# -*- coding: utf-8 -*-
"""Lead: golden pair 2nd pass — derive page mapping & color->ink mapping."""
import struct, collections, sys
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
    blocks = []
    cur = dict(advance=0, records=[])
    pos = 0
    while True:
        i = buf.find(b'\x1b', pos)
        if i < 0 or i + 2 >= len(buf): break
        b1 = buf[i+1]
        if b1 == 0x69 and i + 9 <= len(buf):
            color = buf[i+2]; depth = buf[i+4]
            n = buf[i+5] | (buf[i+6] << 8); m = buf[i+7] | (buf[i+8] << 8)
            raw, j = decode_rle(buf, i+9, n*m)
            cur['records'].append(dict(color=color, depth=depth, n=n, m=m, raw=raw))
            pos = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i+2]; ln = buf[i+3] | (buf[i+4] << 8)
            data = buf[i+5:i+5+ln]
            if cmd == 0x76 and ln >= 4:
                adv = struct.unpack('<I', data[:4])[0]
                if cur['records']:
                    blocks.append(cur)
                cur = dict(advance=adv, records=[])
            pos = i + 5 + ln
        else:
            pos = i + 1
    if cur['records']:
        blocks.append(cur)
    return blocks

def main():
    blocks = parse_prn(PRN)
    print("blocks=%d" % len(blocks))
    pos = 0
    print("block positions:")
    for bi, b in enumerate(blocks):
        pos += b['advance']
        b['pos'] = pos
        print("  b%02d adv=%3d pos=%4d" % (bi, b['advance'], pos))
    # 每个 color 的 ink page-row 集合（p = pos + 8r）
    by_color = collections.defaultdict(list)
    for b in blocks:
        for r in b['records']:
            for y in range(r['m']):
                line = r['raw'][y*r['n']:(y+1)*r['n']]
                if any(line):
                    by_color[r['color']].append(b['pos'] + 8*y)
    print("\n=== color ink page-row ranges (720dpi units) ===")
    for col in sorted(by_color):
        ps = sorted(set(by_color[col]))
        print("color %#04x: rows p=[%d..%d], count=%d, first=%s last=%s" %
              (col, ps[0], ps[-1], len(ps), ps[:6], ps[-6:]))
    # 水平映射（每个 color 的 ink x dots）
    by_x = collections.defaultdict(list)
    for b in blocks:
        for r in b['records']:
            for y in range(r['m']):
                line = r['raw'][y*r['n']:(y+1)*r['n']]
                for byi, byte in enumerate(line):
                    if byte:
                        for bit in range(4):
                            if byte & (0xC0 >> (2*bit)):
                                by_x[r['color']].append(byi*4+bit)
    print("\n=== color ink x ranges (dots at 720dpi) ===")
    for col in sorted(by_x):
        xs = by_x[col]
        print("color %#04x: x=[%d..%d] count=%d" % (col, min(xs), max(xs), len(xs)))

    # 图像特征（红/蓝像素的行列范围 + 每行是否有墨）
    im = Image.open(PNG).convert('RGBA')
    W, H = im.size
    px = im.load()
    rows = {"red": set(), "blue": set(), "ink": set()}
    cols = {"red": set(), "blue": set(), "ink": set()}
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if r > 150 and g < 120 and b < 120:
                rows["red"].add(y); cols["red"].add(x)
            elif b > 100 and r < 120 and g < 120:
                rows["blue"].add(y); cols["blue"].add(x)
            if a != 0 and (r, g, b) != (255, 255, 255):
                rows["ink"].add(y); cols["ink"].add(x)
    print("\n=== PNG features (image pixel coords) ===")
    for k in rows:
        rs = sorted(rows[k]); cs = sorted(cols[k])
        print("%s rows=[%d..%d] cols=[%d..%d] n=%d" % (k, rs[0], rs[-1], cs[0], cs[-1], len(rs)))
    print("\n=== candidate mapping: p = P0 + 6*img_row ; x = X0 + 6*img_col ===")
    # 用 ink 上边缘: 图像 ink 行 25 -> color? 各色 p 范围按 band 分类（红/蓝）
    print("red band page rows:", 6*25, 6*220)
    print("blue band page rows:", 6*385, 6*595)

if __name__ == '__main__':
    main()
