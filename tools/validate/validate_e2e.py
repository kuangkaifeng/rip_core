# -*- coding: utf-8 -*-
"""端到端对拍：mtr_cli 生成 vs 蒙泰 oracle 参考 PRN。
用法: python validate_e2e.py <case1> [case2 ...]
case 形如: flat_white_100_m2 / probe_scan_gray000_m2 ...
"""
import json, os, subprocess, struct, sys, shutil

WS = r"D:\work\RIP核心分析"
CLI = os.path.join(WS, "build", "mtr_cli.exe")
JOBS = os.path.join(WS, "reference", "jobs")
PR = os.path.join(WS, "reference", "prn_samples")
PRS = "D:/work/RIP核心分析/reference/prs/A3-DTF-1390.prs"
OUT = os.path.join(WS, "work", "shared", "e2e")
os.makedirs(OUT, exist_ok=True)


def oracle_job(prn_name):
    stem = prn_name[:-4] if prn_name.endswith(".prn") else prn_name
    return os.path.join(JOBS, stem + ".json")


def run_case(oracle_prn_name):
    stem = oracle_prn_name[:-4] if oracle_prn_name.endswith(".prn") else oracle_prn_name
    oj = oracle_job(stem)
    if not os.path.exists(oj):
        print("MISSING job:", oj)
        return None
    job = json.load(open(oj, encoding="utf-8"))
    out_prn = os.path.join(OUT, "ours_" + stem + ".prn").replace("\\", "/")
    job["prs"] = PRS
    job["output"]["file"]["name"] = out_prn
    job_path = os.path.join(OUT, "job_" + stem + ".json")
    json.dump(job, open(job_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    r = subprocess.run([CLI, "rip", "--job", job_path], capture_output=True, text=True,
                       cwd=os.path.join(WS, "build"))
    ok = r.returncode == 0 and os.path.exists(out_prn)
    return {"ok": ok, "rc": r.returncode, "ours": out_prn,
            "oracle": os.path.join(PR, stem + ".prn"),
            "stderr": r.stderr[-300:] if r.stderr else ""}


def read_prn(path):
    return open(path, "rb").read()


def norm_ti(buf):
    """把 TI 时间戳 8 字节归零（'TI' + len 之后第 1..8 字节）。"""
    i = buf.find(b"TI\x08\x00")
    if i < 0:
        return buf
    b = bytearray(buf)
    for k in range(8):
        if i + 4 + k < len(b):
            b[i + 4 + k] = 0
    return bytes(b)


def decode_page(path, content=384, offsets=None):
    if offsets is None:
        offsets = {0x04: 640, 0x00: 640, 0x12: 644, 0x11: 644}
    buf = read_prn(path)
    q = buf.find(b"\x1b\x00\x00\x00")
    pos = q + 4 if q > 0 else 0
    cmds = {}
    while pos + 2 <= len(buf):
        if buf[pos] != 0x1B:
            pos += 1
            continue
        b1 = buf[pos + 1]
        if b1 == 0x28:
            cmd = buf[pos + 2]
            ln = buf[pos + 3] | (buf[pos + 4] << 8)
            if cmd == 0x24:
                break
            cmds[cmd] = buf[pos + 5:pos + 5 + ln]
            pos += 5 + ln
        else:
            pos += 2
    U = cmds.get(0x55, b"")
    D = cmds.get(0x44, b"")
    pageunit = 2880 // U[0] if U else 720
    rr = (D[0] | (D[1] << 8)) if len(D) >= 4 else 1440
    vv = D[2] if len(D) >= 4 else 16
    vstep = pageunit // (rr // vv)

    def rle(j, need):
        dec = bytearray()
        n = len(buf)
        while j < n and len(dec) < need:
            c = buf[j]
            if c <= 127:
                cnt = c + 1
                dec += buf[j + 1:j + 1 + cnt]
                j += 1 + cnt
            else:
                cnt = 257 - c
                if j + 1 >= n:
                    break
                dec += bytes([buf[j + 1]]) * cnt
                j += 2
        return bytes(dec[:need]), j

    blocks = []
    cur = {"adv": None, "recs": []}
    p2 = pos
    while True:
        i = buf.find(b"\x1b", p2)
        if i < 0 or i + 2 >= len(buf):
            break
        b1 = buf[i + 1]
        if b1 == 0x69 and i + 9 <= len(buf):
            color = buf[i + 2]
            n = buf[i + 5] | (buf[i + 6] << 8)
            m = buf[i + 7] | (buf[i + 8] << 8)
            raw, j = rle(i + 9, n * m)
            cur["recs"].append({"color": color, "n": n, "m": m, "raw": raw})
            p2 = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i + 2]
            ln = buf[i + 3] | (buf[i + 4] << 8)
            if cmd == 0x76 and ln >= 4:
                if cur["recs"]:
                    blocks.append(cur)
                cur = {"adv": struct.unpack("<I", buf[i + 5:i + 9])[0], "recs": []}
            p2 = i + 5 + ln
        else:
            p2 = i + 1
    if cur["recs"]:
        blocks.append(cur)
    p = 0
    for b in blocks:
        if b["adv"] is not None:
            p += b["adv"]
        b["pos"] = p
    canvas = {}
    for b in blocks:
        for rec in b["recs"]:
            c = rec["color"]
            if c not in canvas:
                canvas[c] = [[0] * content for _ in range(content)]
            top = offsets.get(c, 640)
            for row in range(rec["m"]):
                prow = b["pos"] + vstep * row - top
                if not (0 <= prow < content):
                    continue
                line = rec["raw"][row * rec["n"]:(row + 1) * rec["n"]]
                for x in range(content):
                    byte = line[x >> 2] if (x >> 2) < len(line) else 0
                    val = (byte >> (6 - 2 * (x & 3))) & 3
                    if val:
                        canvas[c][prow][x] = val
    return canvas


def compare(case):
    r = run_case(case)
    if not r:
        return
    if not r["ok"]:
        print("%-28s RUN FAILED rc=%s %s" % (case, r["rc"], r["stderr"][:120]))
        return
    a = read_prn(r["oracle"])
    b = read_prn(r["ours"])
    na, nb = norm_ti(a), norm_ti(b)
    byte_eq = (na == nb)
    print("%-28s size oracle=%8d ours=%8d  bytes_equal(normTI)=%s  diff=%d" % (
        case, len(a), len(b), byte_eq,
        sum(1 for x, y in zip(na, nb) if x != y) + abs(len(na) - len(nb))))
    if len(a) <= 200000 or case.startswith("probe_scan_gray"):
        # 页面点阵对拍（内容 384x384，mode2）
        ca = decode_page(r["oracle"])
        cb = decode_page(r["ours"])
        for c in sorted(set(ca) | set(cb)):
            A = ca.get(c)
            B = cb.get(c)
            if A is None or B is None:
                print("   color %02x missing in one" % c)
                continue
            tot = 0
            eq = 0
            ia = ib = 0
            for y in range(384):
                ra, rb = A[y], B[y]
                for x in range(384):
                    va, vb = ra[x], rb[x]
                    if va: ia += 1
                    if vb: ib += 1
                    if va == vb: eq += 1
                    tot += 1
            meanA = sum(sum(row) for row in A) / 147456.0 * 255.0 / 3.0
            meanB = sum(sum(row) for row in B) / 147456.0 * 255.0 / 3.0
            print("   color %02x: match=%.4f inkA=%d inkB=%d vA=%.1f vB=%.1f" %
                  (c, eq / tot, ia, ib, meanA, meanB))


if __name__ == "__main__":
    cases = sys.argv[1:] or ["a3dtf1390_flat_white_100_m2",
                             "probe_scan_gray000_a3dtf1390_m2",
                             "probe_scan_gray128_a3dtf1390_m2"]
    for c in cases:
        compare(c)
