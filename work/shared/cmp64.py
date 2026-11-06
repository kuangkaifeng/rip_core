# -*- coding: utf-8 -*-
import json, subprocess, os, struct, collections
WS = r"D:\work\RIP核心分析"
B = os.path.join(WS, "build", "mtr_cli.exe")
job = json.load(open(os.path.join(WS, "reference", "jobs", "probe_black_64_m2_golden.json"), encoding="utf-8"))
job["prs"] = "D:/work/RIP核心分析/reference/prs/A3-DTF-1390.prs"
job["output"]["file"]["name"] = "D:/work/RIP核心分析/work/shared/ours_black_64_m2.prn"
outjob = os.path.join(WS, "work", "shared", "ours_black_64_m2.json")
json.dump(job, open(outjob, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
r = subprocess.run([B, "rip", "--job", outjob], capture_output=True, text=True, cwd=os.path.join(WS, "build"))
print("rc=", r.returncode, "size=", os.path.getsize(os.path.join(WS, "work", "shared", "ours_black_64_m2.prn")))
print("oracle size=", os.path.getsize(os.path.join(WS, "reference", "prn_samples", "probe_black_64_m2_golden.prn")))

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

def parse_page(path, content_rows=384, content_cols=384, p0=640):
    buf = open(path, "rb").read()
    # 命令区
    q = buf.find(b"\x1b\x00\x00\x00"); pos = q + 4; cmds = {}
    while pos + 2 <= len(buf):
        if buf[pos] != 0x1B: pos += 1; continue
        b1 = buf[pos+1]
        if b1 == 0x28:
            cmd = buf[pos+2]; ln = buf[pos+3] | (buf[pos+4] << 8)
            if cmd == 0x24: break
            cmds[cmd] = buf[pos+5:pos+5+ln]; pos += 5 + ln
        else: pos += 2
    U = cmds.get(0x55, b""); D = cmds.get(0x44, b"")
    pageunit = 2880 // U[0]
    vstep = pageunit // (D[0] | (D[1] << 8)) * (D[2]) if False else pageunit // ((D[0] | (D[1] << 8)) // D[2])
    blocks = []; cur = dict(adv=None, recs=[]); p2 = pos
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
    # 页面点阵：每色 384x384 level
    canvas = {}
    for b in blocks:
        for rec in b["recs"]:
            c = rec["color"]
            if c not in canvas:
                canvas[c] = [[0]*content_cols for _ in range(content_rows)]
            for r in range(rec["m"]):
                prow = b["pos"] + vstep * r - p0
                if not (0 <= prow < content_rows): continue
                line = rec["raw"][r*rec["n"]:(r+1)*rec["n"]]
                for x in range(content_cols):
                    byte = line[x >> 2] if (x >> 2) < len(line) else 0
                    v = (byte >> (6 - 2*(x & 3))) & 3
                    if v:
                        canvas[c][prow][x] = v
    return canvas

oracle = parse_page(os.path.join(WS, "reference", "prn_samples", "probe_black_64_m2_golden.prn"))
ours = parse_page(os.path.join(WS, "work", "shared", "ours_black_64_m2.prn"))
print("colors oracle:", [hex(c) for c in oracle], "ours:", [hex(c) for c in ours])
for c in sorted(set(oracle) | set(ours)):
    A = oracle.get(c); Bm = ours.get(c)
    if A is None or Bm is None:
        print("color %02x missing in one side" % c); continue
    tot = 0; eq = 0; inkA = 0; inkB = 0; both = 0
    for y in range(384):
        ra = A[y]; rb = Bm[y]
        for x in range(384):
            va = ra[x]; vb = rb[x]
            if va: inkA += 1
            if vb: inkB += 1
            if va and vb: both += 1
            if va == vb: eq += 1
            tot += 1
    print("color %02x: match=%.4f inkA=%d inkB=%d both=%d" % (c, eq/tot, inkA, inkB, both))
