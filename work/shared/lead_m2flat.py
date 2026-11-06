# -*- coding: utf-8 -*-
import struct
from collections import Counter
PRN = r"D:\work\RIP核心分析\reference\prn_samples\a3dtf1390_flat_black_100_m2.prn"

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
        cur["recs"].append(dict(color=color, n=n, m=m, raw=raw))
        pos = j
    elif b1 == 0x28 and i + 5 <= len(buf):
        cmd = buf[i+2]; ln = buf[i+3] | (buf[i+4] << 8)
        if cmd == 0x76 and ln >= 4:
            if cur["recs"]: blocks.append(cur)
            cur = dict(adv=struct.unpack("<I", buf[i+5:i+9])[0], recs=[])
        pos = i + 5 + ln
    else:
        pos = i + 1
if cur["recs"]: blocks.append(cur)
print("blocks:", len(blocks))
p = 0
for bi, b in enumerate(blocks):
    if b["adv"] is not None: p += b["adv"]
    b["pos"] = p
    print("block %2d adv=%s pos=%d" % (bi, b["adv"], p))
# ink page rows (p = pos + 8r) 与实际行内容
for col in (0x04, 0x00, 0x12, 0x11):
    ps = []
    for b in blocks:
        for rec in b["recs"]:
            if rec["color"] != col: continue
            for y in range(rec["m"]):
                line = rec["raw"][y*rec["n"]:(y+1)*rec["n"]]
                if any(line):
                    ps.append(b["pos"] + 8*y)
    ps = sorted(set(ps))
    if ps:
        print("color %02x: p=[%d..%d] count=%d" % (col, ps[0], ps[-1], len(ps)))
        # runs
        runs = []; s = ps[0]; pr = ps[0]
        for x in ps[1:]:
            if x == pr + 1: pr = x; continue
            runs.append((s, pr)); s = pr = x
        runs.append((s, pr))
        print("   runs:", runs[:10], "..." if len(runs) > 10 else "")
