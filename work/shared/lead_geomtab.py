# -*- coding: utf-8 -*-
import struct, glob, os, json, re
from collections import Counter
WS = r"D:\work\RIP核心分析"
IN = os.path.join(WS, "reference", "inputs")

def parse(path):
    buf = open(path, "rb").read()
    o = {"file": os.path.basename(path), "size": len(buf)}
    q = buf.find(b"\x1b\x00\x00\x00")
    pos = q + 4 if q > 0 else 0
    stop = buf.find(b"\x1b\x28\x24", pos)
    cmds = {}
    while pos < stop and pos + 2 <= len(buf):
        if buf[pos] != 0x1B:
            pos += 1; continue
        b1 = buf[pos+1]
        if b1 == 0x28:
            cmd = buf[pos+2]; ln = buf[pos+3] | (buf[pos+4] << 8)
            cmds[cmd] = buf[pos+5:pos+5+ln]
            pos += 5 + ln
        else:
            pos += 2
    if 0x53 in cmds and len(cmds[0x53]) == 8:
        o["S"] = struct.unpack("<II", cmds[0x53])
    if 0x63 in cmds and len(cmds[0x63]) == 8:
        o["c"] = struct.unpack("<ii", cmds[0x63])
    if 0x55 in cmds and len(cmds[0x55]) == 5:
        o["U"] = cmds[0x55].hex()
    if 0x44 in cmds and len(cmds[0x44]) == 4:
        o["D"] = cmds[0x44].hex()
    adv = []; blocks = 0; colors = []
    pos = stop
    while True:
        i = buf.find(b"\x1b", pos)
        if i < 0 or i + 2 >= len(buf): break
        b1 = buf[i+1]
        if b1 == 0x69 and i + 9 <= len(buf):
            colors.append(buf[i+2])
            need = (buf[i+5] | (buf[i+6] << 8)) * (buf[i+7] | (buf[i+8] << 8))
            j = i + 9; dec = 0
            while j < len(buf) and dec < need:
                c = buf[j]
                if c <= 127: dec += c + 1; j += 1 + c + 1
                else: dec += 257 - c; j += 2
            pos = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i+2]; ln = buf[i+3] | (buf[i+4] << 8)
            if cmd == 0x76 and ln >= 4:
                adv.append(struct.unpack("<I", buf[i+5:i+9])[0]); blocks += 1
            pos = i + 5 + ln
        else:
            pos = i + 1
    o["blocks"] = blocks + 1
    o["adv"] = adv
    # job json
    jf = os.path.join(WS, "reference", "jobs", os.path.basename(path).replace(".prn", ".json"))
    if os.path.exists(jf):
        j = json.load(open(jf, encoding="utf-8"))
        o["input"] = os.path.basename(j.get("doc", {}).get("name", ""))
        o["modeId"] = j.get("modeId")
    return o

rows = []
for f in sorted(glob.glob(os.path.join(WS, "reference", "prn_samples", "*.prn"))):
    name = os.path.basename(f)
    if not (name.startswith("a3dtf1390_") or name.startswith("geom_") or name.startswith("probe_")): continue
    if os.path.getsize(f) > 2000000: continue
    o = parse(f)
    if "input" not in o: continue
    m = re.match(r".*_m(\d+)", name)
    rows.append((o["input"], name.split("_m")[-1].replace(".prn",""), o.get("blocks"), o.get("S"), o.get("c"), o.get("U"), o.get("D"), list(Counter(o["adv"]).items())[:3], o["size"]))
# 去重：同 input+mode 只留一个
seen = set(); out = []
for r in rows:
    key = (r[0], r[1])
    if key in seen: continue
    seen.add(key); out.append(r)
out.sort(key=lambda r: (r[0], r[1]))
print("%-22s %-6s %5s %14s %16s %-12s %-10s %-28s %8s" % ("input","mode","blk","S(w,h)","c(a,b)","U","D","adv","size"))
for r in out:
    print("%-22s %-6s %5s %14s %16s %-12s %-10s %-28s %8s" % (r[0], r[1], r[2], str(r[3]), str(r[4]), r[5], r[6], str(r[7]), r[8]))
