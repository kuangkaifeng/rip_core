# -*- coding: utf-8 -*-
import json, os, subprocess, struct
WS = r"D:\work\RIP核心分析"
job = json.load(open(os.path.join(WS, "reference", "jobs", "probe_black_64_h13_m0.json"), encoding="utf-8"))
job["prs"] = "D:/work/RIP核心分析/reference/prs/H13 XP600.prs"
out = os.path.join(WS, "work", "shared", "hssf_black64.prn")
job["output"]["file"]["name"] = out.replace("\\", "/")
jp = os.path.join(WS, "work", "shared", "hssf_black64.json")
json.dump(job, open(jp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
r = subprocess.run([os.path.join(WS, "build", "mtr_cli.exe"), "rip", "--job", jp],
                   capture_output=True, text=True, cwd=os.path.join(WS, "build"))
print("rc=", r.returncode, r.stdout.strip(), r.stderr.strip()[:300])
print("ours size:", os.path.getsize(out))
ref = os.path.join(WS, "reference", "prn_samples", "probe_black_64_h13_m0.prn")
print("oracle size:", os.path.getsize(ref))
a = open(out, "rb").read()
b = open(ref, "rb").read()
def hdr(d):
    return dict(zip(["sig","xDPI","yDPI","BPL","H","W","paperW","planes","r0","r1","r2","r3"],
                    struct.unpack("<12I", d[:48])))
ha, hb = hdr(a), hdr(b)
print("ours  hdr:", ha)
print("oracle hdr:", hb)
same = sum(1 for k in ha if ha[k] == hb[k])
print("header fields equal:", same, "/", len(ha))
print("data equal:", a[48:] == b[48:], " data len ours/oracle:", len(a)-48, len(b)-48)
if len(a) == len(b):
    diff = sum(1 for x, y in zip(a[48:], b[48:]) if x != y)
    print("data bytes diff:", diff, "/", len(a)-48)
