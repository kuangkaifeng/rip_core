#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M/K 176x176 x 256-level probes (same spec as C176/Y176).

For each ink in (M, K), t=0..255:
  reference/inputs/probe_scan_<INK>###_176.tif  (176x176 CMYK TIFF, 120 dpi, INK=t)
  reference/prn_samples/probe_scan_<INK>###_176_a3dtf1390_m2.prn  (A3 mode2)
Merged into work/protocol/evidence/probe_scan_manifest.json as kind M176/K176.
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


def health():
    try:
        return O.get("/mtrip/v1/status").get("result") == 0
    except Exception:
        return False


def main():
    plan = []
    print("generating 512 inputs ...", flush=True)
    for ink, kw in (("M", "m"), ("K", "k")):
        for t in range(256):
            tag = "%s%03d" % (ink, t)
            img = os.path.join(O.INPUTS, "probe_scan_%s_176.tif" % tag)
            Image.new("CMYK", (SIZE, SIZE), tuple(
                t if key == kw else 0 for key in ("c", "m", "y", "k"))
            ).save(img, "TIFF", dpi=DPI)
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
            rec = {"kind": ink + "176", "tag": tag,
                   "input": img.replace("\\", "/"), "prn": out,
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

    man = json.load(open(MAN, encoding="utf-8"))
    man["jobs"] = man["jobs"] + rows
    man["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    man.setdefault("tile176", {})
    man["tile176"]["mk"] = {"total": len(rows),
                            "ok": sum(1 for r in rows if r.get("result") == 0),
                            "note": "M/K 256-level 176x176 scans"}
    with open(MAN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    ok = sum(1 for r in rows if r.get("result") == 0)
    print("\nmerged manifest: %d jobs total; this run %d ok/%d, PRN %.2f MB, %.0fs"
          % (len(man["jobs"]), ok, len(rows),
             sum(r.get("size") or 0 for r in rows) / 1048576.0, time.time() - t0))
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
