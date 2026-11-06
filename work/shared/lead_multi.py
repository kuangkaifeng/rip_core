# -*- coding: utf-8 -*-
import struct
from collections import defaultdict
PRN = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"

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

buf = open(PRN, "rb").read()
q = buf.find(b"\x1b\x00\x00\x00")
stop = buf.find(b"\x1b\x28\x24", q + 4)
pos = stop
blocks = []; cur = dict(adv=None, recs=[])
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
if cur["recs"]: blocks.append(cur)
p = 0
for b in blocks:
    if b["adv"] is not None: p += b["adv"]
    b["pos"] = p
# 记录 -> p 映射（每色）
rowmap = defaultdict(list)   # p -> [(bidx, r)]
for b in blocks:
    for r in range(90):
        rowmap[b["pos"] + 8*r].append((blocks.index(b) if False else b, r))

def bits(rec, r):
    line = rec["raw"][r*rec["n"]:(r+1)*rec["n"]]
    out = []
    for byte in line:
        out += [(byte >> 6) & 3, (byte >> 4) & 3, (byte >> 2) & 3, byte & 3]
    return out

def get_rec(b, color):
    for rec in b["recs"]:
        if rec["color"] == color: return rec
    return None

# 找 multi 覆盖的 p（内容区内），比较内容是否一致
multis = [(p, v) for p, v in rowmap.items() if len(v) > 1 and 700 <= p <= 4200]
multis.sort()
print("multi-covered content rows:", len(multis), "first:", multis[:3])
import random
random.seed(2)
same_cnt = 0; diff_cnt = 0; examine = 0
for p, v in random.sample(multis, min(30, len(multis))):
    b1, r1 = v[0]; b2, r2 = v[1]
    # 用第一色比较
    c = blocks[0]["recs"][0]["color"]
    m1 = bits(get_rec(b1, c), r1); m2 = bits(get_rec(b2, c), r2)
    eq = sum(1 for a, b in zip(m1, m2) if a == b)
    inter = sum(1 for a, b in zip(m1, m2) if a and b)
    u1 = sum(1 for a in m1 if a); u2 = sum(1 for a in m2 if a)
    examine += 1
    if u1 == 0 and u2 == 0: continue
    ratio = eq / len(m1)
    if ratio > 0.999: same_cnt += 1
    else: diff_cnt += 1
    if examine <= 8:
        print("p=%d blocks=(%d,r%d) vs (%d,r%d) same_ratio=%.4f ink1=%d ink2=%d both=%d" %
              (p, blocks.index(b1) if b1 in blocks else -1, r1, blocks.index(b2) if b2 in blocks else -1, r2, ratio, u1, u2, inter))
print("same:", same_cnt, "diff:", diff_cnt)
