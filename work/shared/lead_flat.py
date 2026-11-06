# -*- coding: utf-8 -*-
import struct, glob, os
from collections import Counter
WS = r"D:\work\RIP核心分析"
PR = os.path.join(WS, "reference", "prn_samples")

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

def parse(path, maxblocks=3):
    buf = open(path, "rb").read()
    q = buf.find(b"\x1b\x00\x00\x00")
    stop = buf.find(b"\x1b\x28\x24", q + 4)
    pos = stop; blocks = []; cur = dict(adv=None, recs=[])
    while True:
        i = buf.find(b"\x1b", pos)
        if i < 0 or i + 2 >= len(buf): break
        b1 = buf[i+1]
        if b1 == 0x69 and i + 9 <= len(buf):
            color = buf[i+2]; n = buf[i+5] | (buf[i+6] << 8); m = buf[i+7] | (buf[i+8] << 8)
            raw, j = decode_rle(buf, i+9, n*m)
            cur["recs"].append(dict(color=color, n=n, m=m, raw=raw)); pos = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i+2]; ln = buf[i+3] | (buf[i+4] << 8)
            if cmd == 0x76 and ln >= 4:
                if cur["recs"]: blocks.append(cur)
                cur = dict(adv=struct.unpack("<I", buf[i+5:i+9])[0], recs=[])
            pos = i + 5 + ln
        else:
            pos = i + 1
        if len(blocks) >= maxblocks: break
    if cur["recs"] and len(blocks) < maxblocks: blocks.append(cur)
    return blocks

def bits(raw):
    out = []
    for byte in raw:
        out += [(byte >> 6) & 3, (byte >> 4) & 3, (byte >> 2) & 3, byte & 3]
    return out

names = ["flat_r_100","flat_g_100","flat_b_100","flat_c_100","flat_m_100","flat_y_100","flat_k_100","flat_black_100","flat_white_100","rgb_quad_100","cmyk_quad_100"]
for nm in names:
    f = os.path.join(PR, "a3dtf1390_%s_m2.prn" % nm)
    if not os.path.exists(f): 
        print(nm, "MISSING"); continue
    blocks = parse(f, 2)
    # 用中间块的第 85 行（内容行）统计每色墨点
    b = blocks[0]
    # 找有数据块：这里直接统计所有记录
    for rec in b["recs"]:
        m = rec["m"]; n = rec["n"]
        total = 0; vals = Counter()
        for y in range(80, 90):
            line = rec["raw"][y*n:(y+1)*n]
            for byte in line:
                if byte:
                    for k in range(4):
                        v = (byte >> (6-2*k)) & 3
                        if v: vals[v] += 1; total += 1
        print("%-14s color %02x: ink_dots(last10rows)=%5d vals=%s" % (nm, rec["color"], total, dict(vals)))
    print()
