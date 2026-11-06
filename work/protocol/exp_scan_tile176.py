#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FINAL dataset gap: C/Y 256-level probes on 176x176 CMYK TIFF.

Content = 176 px @120 dpi -> 1056x1056 output pixels at mode2 (720x720 dpi),
i.e. > 1024x1024, enough to cover the full 1024x1024 threshold tile.

Naming (NOTE: PRN stem gets an explicit "_176" suffix so the existing 64x64
probe-scan PRNs `probe_scan_C###_a3dtf1390_m2.prn` are NOT overwritten):
  reference/inputs/probe_scan_C###_176.tif / probe_scan_Y###_176.tif
  reference/prn_samples/probe_scan_C###_176_a3dtf1390_m2.prn  (same for Y)
  reference/jobs/probe_scan_C###_176_a3dtf1390_m2.{json,resp.json}

Merged into work/protocol/evidence/probe_scan_manifest.json as kind C176 / Y176.
Sequential POST only.
"""
import json
import os
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

EV = os.path.join(HERE, "evidence")
MAN = os.path.join(EV, "probe_scan_manifest.json")
DPI = (120, 120)
PRS = "./A3-DTF-1390.prs"
SIZE = 176


def mk(name, c=0, m=0, y=0, k=0):
    path = os.path.join(O.INPUTS, name)
    Image.new("CMYK", (SIZE, SIZE), (c, m, y, k)).save(path, "TIFF", dpi=DPI)
    return path


def health():
    try:
        return O.get("/mtrip/v1/status").get("result") == 0
    except Exception:
        return False


def main():
    plan = []
    print("generating 512 inputs ...", flush=True)
    for ink, kw in (("C", "c"), ("Y", "y")):
        for t in range(256):
            tag = "%s%03d" % (ink, t)
            img = mk("probe_scan_%s_176.tif" % tag, **{kw: t})
            plan.append((ink, tag, img))
    total = len(plan)
    print("total jobs:", total, flush=True)

    rows = []
    t0 = time.time()
    for i, (ink, tag, img) in enumerate(plan, 1):
        if i % 50 == 0 and not health():
            print("!! oracle not healthy at %d, stop" % i, flush=True)
            break
        stem = "probe_scan_%s_176_a3dtf1390_m2" % tag
        out = os.path.join(O.PRNS, stem + ".prn").replace("\\", "/")
        job = O.build_job(img.replace("\\", "/"), PRS, 2, out)
        try:
            r = O.run_job(job, stem)
            rec = {"kind": ink + "176", "tag": tag, "input": img.replace("\\", "/"),
                   "prn": out,
                   "job": os.path.join(O.JOBS, stem + ".json").replace("\\", "/"),
                   "result": r["response"].get("result"),
                   "error": r["response"].get("error"),
                   "size": r["prn_size"],
                   "elapsed_s": r["response"].get("_elapsed_s")}
        except Exception as e:
            rec = {"kind": ink + "176", "tag": tag, "input": img, "prn": out,
                   "result": "CONN_ERR", "error": repr(e), "size": 0}
        rows.append(rec)
        if i % 25 == 0 or i == total:
            ok = sum(1 for x in rows if x.get("result") == 0)
            sz = sum(x.get("size") or 0 for x in rows) / 1048576.0
            print("  %d/%d ok=%d prn=%.1fMB (%.0fs)" % (
                i, total, ok, sz, time.time() - t0), flush=True)

    # merge manifest (append; C176/Y176 kinds are new, no collision)
    man = json.load(open(MAN, encoding="utf-8"))
    man["jobs"] = man["jobs"] + rows
    man["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    man["tile176"] = {"note": "C/Y 256-level probes on 176x176 (content 1056x1056 px "
                              "covers the full 1024x1024 threshold tile)",
                      "total": len(rows),
                      "ok": sum(1 for r in rows if r.get("result") == 0),
                      "prn_naming": "probe_scan_<C|Y>###_176_a3dtf1390_m2.prn "
                                    "(explicit _176 keeps 64x64 probes intact)"}
    with open(MAN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    ok = sum(1 for r in rows if r.get("result") == 0)
    sz = sum(r.get("size") or 0 for r in rows) / 1048576.0
    print("\nmerged manifest: %d jobs total; this run %d ok/%d, PRN %.2f MB, %.0fs"
          % (len(man["jobs"]), ok, len(rows), sz, time.time() - t0))
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
