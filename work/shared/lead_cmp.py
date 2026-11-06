# -*- coding: utf-8 -*-
import struct, collections

def parse(path):
    buf = open(path, "rb").read()
    q = buf.find(b"\x1b\x00\x00\x00")
    cmdstart = q + 4
    # command list
    cmds = []
    pos = cmdstart
    while pos + 2 <= len(buf):
        if buf[pos] != 0x1B:
            pos += 1; continue
        b1 = buf[pos+1]
        if b1 == 0x28:
            cmd = buf[pos+2]; ln = buf[pos+3] | (buf[pos+4] << 8)
            if cmd == 0x24: break
            cmds.append((cmd, ln, buf[pos+5:pos+5+ln].hex()))
            pos += 5 + ln
        elif b1 == 0x55:
            cmds.append(("ESCU", 1, buf[pos+2:pos+3].hex())); pos += 3
        elif b1 == 0x40:
            cmds.append(("ESCat", 0, "")); pos += 2
        else:
            pos += 2
    # blocks
    stream = pos
    blocks = []; cur = dict(adv=None, recs=[]); p2 = stream
    def premap(t):
        if t == 0x55: return "U"
        return chr(t)
    while True:
        i = buf.find(b"\x1b", p2)
        if i < 0 or i + 2 >= len(buf): break
        b1 = buf[i+1]
        if b1 == 0x69 and i + 9 <= len(buf):
            color = buf[i+2]; n = buf[i+5] | (buf[i+6] << 8); m = buf[i+7] | (buf[i+8] << 8)
            need = n * m; j = i + 9; dec = 0
            while j < len(buf) and dec < need:
                c = buf[j]
                if c <= 127: dec += c + 1; j += 1 + c + 1
                else: dec += 257 - c; j += 2
            cur["recs"].append((color, n, m)); p2 = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i+2]; ln = buf[i+3] | (buf[i+4] << 8)
            if cmd == 0x76 and ln >= 4:
                if cur["recs"]: blocks.append(cur)
                cur = dict(adv=struct.unpack("<I", buf[i+5:i+9])[0], recs=[])
            p2 = i + 5 + ln
        else: p2 = i + 1
    if cur["recs"]: blocks.append(cur)
    return dict(size=len(buf), cmds=cmds, blocks=blocks,
                colors=[c for c, _, _ in blocks[0]["recs"]] if blocks else [],
                adv=collections.Counter(b["adv"] for b in blocks[1:]).most_common(4),
                recs_per_block=collections.Counter(len(b["recs"]) for b in blocks).most_common(3),
                first_adv=blocks[0]["adv"] if blocks else None)

ORACLE = r"D:\work\RIP核心分析\reference\prn_samples\a3dtf1390_flat_black_100_m2.prn"
OURS = r"D:\work\RIP核心分析\work\shared\ours_flat_black_100_m2.prn"
o = parse(ORACLE); u = parse(OURS)
print("ORACLE: size=%d blocks=%d colors=%s adv=%s recs/blk=%s first_adv=%s" % (o["size"], len(o["blocks"]), [hex(c) for c in o["colors"]], o["adv"], o["recs_per_block"], o["first_adv"]))
print("OURS  : size=%d blocks=%d colors=%s adv=%s recs/blk=%s first_adv=%s" % (u["size"], len(u["blocks"]), [hex(c) for c in u["colors"]], u["adv"], u["recs_per_block"], u["first_adv"]))
print("\ncommand region compare:")
for i in range(max(len(o["cmds"]), len(u["cmds"]))):
    a = o["cmds"][i] if i < len(o["cmds"]) else None
    b = u["cmds"][i] if i < len(u["cmds"]) else None
    same = "OK" if a == b else "DIFF"
    print("  %-4s oracle=%-36s ours=%-36s" % (same, str(a), str(b)))
