# -*- coding: utf-8 -*-
import json, subprocess, os, struct
WS = r"D:\work\RIP核心分析"
job = json.load(open(os.path.join(WS, "reference", "jobs", "probe_black_64_m2_golden.json"), encoding="utf-8"))
job["prs"] = "D:/work/RIP核心分析/reference/prs/A3-DTF-1390.prs"
job["output"]["file"]["name"] = "D:/work/RIP核心分析/work/shared/ours_black_64_m2.prn"
outjob = os.path.join(WS, "work", "shared", "ours_black_64_m2.json")
json.dump(job, open(outjob, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
r = subprocess.run([os.path.join(WS, "build", "mtr_cli.exe"), "rip", "--job", outjob],
                   capture_output=True, text=True, cwd=os.path.join(WS, "build"))
print("run rc=", r.returncode, r.stdout.strip(), r.stderr.strip()[:500])
print("our size:", os.path.getsize(os.path.join(WS, "work", "shared", "ours_black_64_m2.prn")))
print("oracle size:", os.path.getsize(os.path.join(WS, "reference", "prn_samples", "probe_black_64_m2_golden.prn")))
