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
# p -> list (bidx, r)
rowmap = defaultdict(list)
for bi, b in enumerate(blocks):
    for r in range(90):
        rowmap[b["pos"] + 8*r].append((bi, r))
multis = sorted([p for p, v in rowmap.items() if len(v) > 1 and 800 <= p <= 4200])
print("multi rows:", len(multis), "sample:", multis[:5])

def bits_at(bi, r, color):
    for rec in blocks[bi]["recs"]:
        if rec["color"] != color: continue
        line = rec["raw"][r*rec["n"]:(r+1)*rec["n"]]
        out = []
        for byte in line:
            out += [(byte >> 6) & 3, (byte >> 4) & 3, (byte >> 2) & 3, byte & 3]
        return out
    return None

# 选一个多覆盖且在红带(内容密集)的行
target = [p for p in multis if 900 <= p <= 1300]
print("candidates in red band:", target[:10])
for p in target[:3]:
    (b1, r1), (b2, r2) = rowmap[p][0], rowmap[p][1]
    color = 0x11  # Y (red 区域有墨)
    A = bits_at(b1, r1, color); B = bits_at(b2, r2, color)
    if A is None or B is None: continue
    ai = [i for i, v in enumerate(A) if v]
    bi_ = [i for i, v in enumerate(B) if v]
    both = [i for i in ai if B[i]]
    print("\np=%d blocks (%d,r%d) vs (%d,r%d) color=%02x inkA=%d inkB=%d both=%d" % (p, b1, r1, b2, r2, color, len(ai), len(bi_), len(both)))
    # x 位置 mod 特征
    import collections
    print(" A mod2:", collections.Counter(i % 2 for i in ai).most_common(), " B mod2:", collections.Counter(i % 2 for i in bi_).most_common())
    print(" A mod4:", collections.Counter(i % 4 for i in ai).most_common(), " B mod4:", collections.Counter(i % 4 for i in bi_).most_common())
    # A 值分布
    print(" A vals:", collections.Counter(A[i] for i in ai).most_common(), " B vals:", collections.Counter(B[i] for i in bi_).most_common())
    # 打印前 80 个 dot 的 A/B 归属模式（1=A,2=B,0=none）
    pat = []
    for x in range(0, 200):
        pat.append('A' if A[x] else ('B' if B[x] else '.'))
    print(" pattern x0..199:", "".join(pat))
