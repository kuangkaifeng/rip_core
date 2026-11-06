# -*- coding: utf-8 -*-
import struct
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
for bi, b in enumerate(blocks):
    if b["adv"] is not None: p += b["adv"]
    b["pos"] = p
for bi, b in enumerate(blocks):
    out = []
    for rec in b["recs"][:1]:  # 只看第一色
        rows = [y for y in range(rec["m"]) if any(rec["raw"][y*rec["n"]:(y+1)*rec["n"]])]
        # 数据行里的 x 范围
        xr = None
        for y in rows:
            line = rec["raw"][y*rec["n"]:(y+1)*rec["n"]]
            for i, byte in enumerate(line):
                if byte:
                    xr = (i*4, i*4+3) if xr is None else (xr[0], i*4+3)
        out.append("c=%02x rows=%d [%s..%s] x=%s" % (rec["color"], len(rows), rows[0] if rows else "-", rows[-1] if rows else "-", xr))
    print("block %2d pos=%4d  %s" % (bi, b["pos"], " | ".join(out)))
