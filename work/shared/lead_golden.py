# -*- coding: utf-8 -*-
"""Lead: golden pair geometry analysis.
PRN: 1793946733280.prn (A3-DTF-1390, modeId=2)
PNG: 1793946733018.png (718x654 RGBA; red 'SNS' top, blue '10' bottom, white/transparent bg)
"""
import sys, struct, collections, os, json

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
    blocks = []   # list of dict(advance, records list)
    cur = dict(advance=None, records=[])
    pos = 0
    first = True
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
    print("blocks:", len(blocks))
    print("advances:", collections.Counter(b['advance'] for b in blocks).most_common(10))
    # 颜色
    colors = collections.Counter()
    for b in blocks:
        for r in b['records']:
            colors[r['color']] += 1
    print("colors:", {hex(k): v for k, v in colors.items()})
    # 每色：总墨量 + x 范围 + 出现的块/行范围
    for col in sorted(colors):
        tot = 0; xmin = 10**9; xmax = -1
        rowmin = 10**9; rowmax = -1
        blocks_with = set()
        # 墨量按 x 投影
        xprof = collections.Counter()
        for bi, b in enumerate(blocks):
            for r in b['records']:
                if r['color'] != col: continue
                for y in range(r['m']):
                    line = r['raw'][y*r['n']:(y+1)*r['n']]
                    for byi, byte in enumerate(line):
                        if byte:
                            blocks_with.add(bi)
                            xmin = min(xmin, byi*4); xmax = max(xmax, byi*4+3)
                            tot += 1
                            rowmin = min(rowmin, y); rowmax = max(rowmax, y)
        print("color %#04x: ink_bytes=%d x=[%d..%d] blockrows=[%d..%d] blocks=%d" %
              (col, tot, xmin, xmax, rowmin, rowmax, len(blocks_with)))

    # 用 PNG 行分类：红行、蓝行
    from PIL import Image
    im = Image.open(PNG).convert('RGBA')
    W, H = im.size
    px = im.load()
    red_rows = collections.Counter(); blue_rows = collections.Counter()
    dark_rows = collections.Counter()
    alpha_rows = collections.Counter()
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if a == 0:
                alpha_rows[y] += 1
                continue
            if r > 150 and g < 120 and b < 120: red_rows[y] += 1
            elif b > 100 and r < 120 and g < 120: blue_rows[y] += 1
            if (r+g+b) < 600: dark_rows[y] += 1
    def rng(c):
        ks = sorted(k for k, v in c.items() if v > 0)
        return (ks[0], ks[-1], len(ks)) if ks else None
    print("PNG size", W, H)
    print("red rows", rng(red_rows), "blue rows", rng(blue_rows), "dark rows", rng(dark_rows))
    print("transparent rows", rng(alpha_rows))
    # 对比：每个 color 的"有墨 raster 行集合" 在页面中的 y 分布
    # 先输出每个 color 在每个块内"有墨行数"统计表（竖直方向签名）
    print("\n=== per-block per-color ink row counts (block: adv, [c:count]) ===")
    for bi, b in enumerate(blocks[:12]):
        parts = []
        for r in b['records']:
            cnt = sum(1 for y in range(r['m']) if any(r['raw'][y*r['n']:(y+1)*r['n']]))
            ys = [y for y in range(r['m']) if any(r['raw'][y*r['n']:(y+1)*r['n']])]
            parts.append("%02x:%d(%s..%s)" % (r['color'], cnt, ys[0] if ys else '-', ys[-1] if ys else '-'))
        print(" block %2d adv=%s  %s" % (bi, b['advance'], "  ".join(parts)))

if __name__ == '__main__':
    main()
