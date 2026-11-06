# -*- coding: utf-8 -*-
import struct, glob, os, json
from collections import Counter
from PIL import Image
WS = r"D:\work\RIP核心分析"
PR = os.path.join(WS, "reference", "prn_samples")
JO = os.path.join(WS, "reference", "jobs")

def parse(path):
    buf = open(path, "rb").read()
    o = {}
    q = buf.find(b"\x1b\x00\x00\x00")
    pos = q + 4 if q > 0 else 0
    stop = buf.find(b"\x1b\x28\x24", pos)
    cmds = {}
    while pos < stop and pos + 2 <= len(buf):
        if buf[pos] != 0x1B: pos += 1; continue
        b1 = buf[pos+1]
        if b1 == 0x28:
            cmd = buf[pos+2]; ln = buf[pos+3] | (buf[pos+4] << 8)
            cmds[cmd] = buf[pos+5:pos+5+ln]; pos += 5 + ln
        else: pos += 2
    if 0x53 in cmds: o["S"] = struct.unpack("<II", cmds[0x53])
    if 0x63 in cmds: o["c"] = struct.unpack("<ii", cmds[0x63])
    if 0x55 in cmds: o["U"] = cmds[0x55].hex()
    if 0x44 in cmds: o["D"] = cmds[0x44].hex()
    if 0x65 in cmds: o["e"] = cmds[0x65].hex()
    if 0x4B in cmds: o["K"] = cmds[0x4B].hex()
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
        else: pos = i + 1
    o["blocks"] = blocks + 1
    o["adv"] = adv
    o["colors"] = sorted(set(colors))
    o["recs"] = len(colors)
    return o

def get_job(prn):
    jf = os.path.join(JO, os.path.basename(prn).replace(".prn", ".json"))
    if not os.path.exists(jf): return None
    j = json.load(open(jf, encoding="utf-8"))
    p = j.get("doc", {}).get("name", "")
    info = {}
    if p and os.path.exists(p):
        try:
            im = Image.open(p); info["px"] = im.size; info["dpi"] = im.info.get("dpi")
        except Exception: pass
    info["modeId"] = j.get("modeId")
    return info

print("%-40s %-10s %-6s %-6s %10s %8s %5s %8s %-12s %-10s %s" % ("prn","img","mode","blocks","S","c","recs","adv0","U","D","colors"))
for f in sorted(glob.glob(os.path.join(PR, "a3dtf1390_*.prn"))):
    nm = os.path.basename(f)
    if not any(k in nm for k in ("_100_m", "_720_m", "64")): continue
    try: o = parse(f)
    except Exception as e: print(nm, "ERR", e); continue
    j = get_job(f) or {}
    px = j.get("px"); img = "%dx%d" % px if px else "?"
    adv = o["adv"]
    print("%-40s %-10s %-6s %-6d %-10s %-10s %5d %8s %-12s %-10s %s" % (
        nm, img, str(j.get("modeId")), o["blocks"], str(o.get("S")), str(o.get("c")), o["recs"],
        str(adv[:3]) + ("..." if len(adv) > 3 else ""), o.get("U"), o.get("D"), [hex(c) for c in o["colors"]]))
