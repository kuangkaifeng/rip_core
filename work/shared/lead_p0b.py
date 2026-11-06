# -*- coding: utf-8 -*-
import struct, os
B = r"D:\work\RIP核心分析\reference\prn_samples"

def decode_rle(buf, j, need):
    dec = bytearray(); n = len(buf)
    while j < n and len(dec) < need:
        c = buf[j]
        if c <= 127:
            cnt = c + 1; dec += buf[j+1:j+1+cnt]; j += 1 + cnt
        else:
            cnt = 257 - c
            if j+1 >= n: break
            dec += bytes([buf[j+1]]) * cnt; j += 2
    return bytes(dec[:need]), j

def parse(path):
    buf = open(path, "rb").read()
    q = buf.find(b"\x1b\x00\x00\x00")
    pos = q + 4 if q > 0 else 0
    cmds = {}
    while pos + 2 <= len(buf):
        if buf[pos] != 0x1B: pos += 1; continue
        b1 = buf[pos+1]
        if b1 == 0x28:
            cmd = buf[pos+2]; ln = buf[pos+3] | (buf[pos+4] << 8)
            if cmd == 0x24: break  # command region ends
            cmds[cmd] = buf[pos+5:pos+5+ln]; pos += 5 + ln
        elif b1 == 0x55:
            cmds[0x55] = bytes([buf[pos+2]]); pos += 3
        else: pos += 2
    U = cmds.get(0x55, b""); D = cmds.get(0x44, b""); S = cmds.get(0x53, b""); c = cmds.get(0x63, b"")
    pageunit = 2880 // U[0] if len(U) >= 5 and U[0] else None
    r = (D[0] | (D[1] << 8)) if len(D) >= 4 else 1440
    v = D[2] if len(D) >= 4 else 16
    vraster = r // v
    vstep = pageunit // vraster if pageunit and vraster else None
    # block stream starts right after command region: find last of ESC(m),ESC(V) then
    start = buf.find(b"\x1b\x00\x00\x00") + 4
    # 从命令区末尾的 ESC ( V 之后开始（ESC( V 是命令区最后一条）
    iV = buf.find(b"\x1b\x28\x56", start)
    stream = iV + 5 + (buf[iV+3] | (buf[iV+4] << 8)) if iV > 0 else start
    blocks = []; cur = dict(adv=None, recs=[]); p2 = stream
    while True:
        i = buf.find(b"\x1b", p2)
        if i < 0 or i + 2 >= len(buf): break
        b1 = buf[i+1]
        if b1 == 0x69 and i + 9 <= len(buf):
            color = buf[i+2]; n = buf[i+5] | (buf[i+6] << 8); m = buf[i+7] | (buf[i+8] << 8)
            raw, j = decode_rle(buf, i+9, n*m)
            cur["recs"].append(dict(color=color, n=n, m=m, raw=raw)); p2 = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i+2]; ln = buf[i+3] | (buf[i+4] << 8)
            if cmd == 0x76 and ln >= 4:
                if cur["recs"]: blocks.append(cur)
                cur = dict(adv=struct.unpack("<I", buf[i+5:i+9])[0], recs=[])
            p2 = i + 5 + ln
        else: p2 = i + 1
    if cur["recs"]: blocks.append(cur)
    p = 0
    for b in blocks:
        if b["adv"] is not None: p += b["adv"]
        b["pos"] = p
    ps = []
    for b in blocks:
        for rec in b["recs"]:
            for y in range(rec["m"]):
                if any(rec["raw"][y*rec["n"]:(y+1)*rec["n"]]):
                    ps.append(b["pos"] + vstep*y)
    ps = sorted(set(ps))
    return dict(pageunit=pageunit, vstep=vstep, blocks=len(blocks), pos0=blocks[0]["pos"] if blocks else None,
                p_min=ps[0] if ps else None, p_max=ps[-1] if ps else None,
                S=struct.unpack("<II", S) if len(S)==8 else None,
                c=struct.unpack("<ii", c) if len(c)==8 else None,
                adv=[b["adv"] for b in blocks[:3]])

for nm in ["a3dtf1390_flat_black_100_m0","a3dtf1390_flat_black_100_m1","a3dtf1390_flat_black_100_m2","a3dtf1390_flat_black_100_m3","a3dtf1390_flat_black_64_m2","a3dtf1390_flat_black_720_m2","golden_repro_1793946733280"]:
    p = os.path.join(B, nm + ".prn")
    if not os.path.exists(p):
        print(nm, "MISSING"); continue
    o = parse(p)
    print("%-34s unit=%-4s vstep=%-2s blocks=%-3d pos0=%-4s adv0=%s p_min=%-5s p_max=%-5s S=%s c=%s" % (
        nm, o["pageunit"], o["vstep"], o["blocks"], o["pos0"], o["adv"][:2], o["p_min"], o["p_max"], o["S"], o["c"]))
