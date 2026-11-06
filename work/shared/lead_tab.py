# -*- coding: utf-8 -*-
import struct, glob, os, json
WS = r"D:\work\RIP核心分析"

def parse_cmd(path):
    buf = open(path, "rb").read()
    out = {"file": os.path.basename(path), "size": len(buf)}
    # remote TI/JS/JH
    q = buf.find(b"\x1b\x00\x00\x00")
    if q > 0:
        s = buf.find(b"REMOTE1")
        if s >= 0:
            pos = s + 7
            while pos + 4 <= q:
                cmd = buf[pos:pos+2].decode("latin1"); ln = buf[pos+2] | (buf[pos+3] << 8)
                data = buf[pos+4:pos+4+ln]
                if cmd in ("TI", "JS", "JH"):
                    out[cmd] = data.hex()
                pos += 4 + ln
    # command region
    pos = q + 4 if q > 0 else 0
    stop = buf.find(b"\x1b\x28\x24", pos)
    cmds = {}
    while pos < stop and pos + 2 <= len(buf):
        if buf[pos] != 0x1B:
            pos += 1; continue
        b1 = buf[pos+1]
        if b1 == 0x28:
            cmd = buf[pos+2]; ln = buf[pos+3] | (buf[pos+4] << 8)
            data = buf[pos+5:pos+5+ln]
            cmds["%c"%cmd] = data.hex()
            pos += 5 + ln
        elif b1 in (0x55, 0x40):
            cmds["esc%02x"%b1] = buf[pos+2:pos+3].hex()
            pos += 3 if b1 == 0x55 else 2
        else:
            pos += 2
    for k in ("U","D","c","S","m","K","e","G","i"):
        if k in cmds:
            out["ESC(" + k] = cmds[k]
    # block/record stats
    blocks = 0; colors = []; nset = set(); mset = set(); adv = []
    pos = stop if stop > 0 else 0
    while True:
        i = buf.find(b"\x1b", pos)
        if i < 0 or i + 2 >= len(buf): break
        b1 = buf[i+1]
        if b1 == 0x69 and i + 9 <= len(buf):
            colors.append(buf[i+2]); nset.add(buf[i+5] | (buf[i+6] << 8)); mset.add(buf[i+7] | (buf[i+8] << 8))
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
    out["blocks+1"] = blocks + 1
    out["records"] = len(colors)
    out["colors"] = sorted(set(colors))
    out["n"] = sorted(nset); out["m"] = sorted(mset)
    from collections import Counter
    out["adv"] = Counter(adv).most_common(4)
    # 找 job json 里的输入图
    jf = os.path.join(WS, "reference", "jobs", os.path.basename(path).replace(".prn", ".json"))
    if os.path.exists(jf):
        try:
            j = json.load(open(jf, encoding="utf-8"))
            out["input"] = os.path.basename(j.get("doc", {}).get("name", ""))
            out["modeId"] = j.get("modeId")
        except Exception as e:
            out["input"] = "?"
    return out

files = sorted(glob.glob(os.path.join(WS, "reference", "prn_samples", "*.prn")))
for f in files:
    if os.path.getsize(f) > 2000000: continue
    try:
        o = parse_cmd(f)
    except Exception as e:
        print("ERR", f, e); continue
    print("%-38s in=%-22s m=%s sz=%8d blocks=%3d recs=%3d n=%s m=%s cols=%s adv=%s D=%s S=%s c=%s e=%s K=%s U=%s" % (
        o["file"], o.get("input","?"), o.get("modeId","?"), o["size"], o.get("blocks+1",0), o["records"],
        o["n"], o["m"], [hex(c) for c in o["colors"]], o["adv"], o.get("ESC(D"), o.get("ESC(S"), o.get("ESC(c"), o.get("ESC(e"), o.get("ESC(K"), o.get("ESC(U")))
