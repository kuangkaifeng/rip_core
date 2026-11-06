#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sequentially run a batch of RIP jobs (for cross-analyst sample requests).

Spec file (JSON) example -- every entry keys off the standard templates:
{
  "note": "requested by escp2-analyst",
  "jobs": [
    {"stem": "geomh_mode2", "image": "D:/work/RIP核心分析/work/escp2/probes/geomh.png",
     "machine": "a3dtf1390", "mode": 2, "variant": "golden"},
    {"stem": "geomh_mode0", "image": ".../geomh.png", "machine": "a3dtf1390",
     "mode": 0, "variant": "golden"}
  ]
}

variant: base (no extra channels) | golden (inputColorEditor W1 full + inkIE
index 4 invaginate 10/10/10/10) | w1w2 | color | smooth
extra per-job overrides are also accepted: rotate, scale, margin, mirror,
dpi, id, extra (dict merged into the job), ice (inputColorEditor array),
inkie (inkIE array).

Outputs: reference/prn_samples/<stem>.prn  reference/jobs/<stem>.json
         reference/jobs/<stem>.resp.json  and a summary JSON printed at end.

Usage:
    python tools/oracle/run_batch.py --spec tools/oracle/requests/xxx.json
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import mtrip_oracle as O   # noqa: E402

MACHINE_PRS = {
    "a3dtf1390": "./A3-DTF-1390.prs",
    "h13xp600": O.PRS["h13xp600"],
    "h13xp600_myicc": O.PRS["h13xp600_myicc"],
}


def run_spec(spec, outdir_prn=None, outdir_jobs=None):
    prns = outdir_prn or O.PRNS
    jobs = outdir_jobs or O.JOBS
    os.makedirs(prns, exist_ok=True)
    os.makedirs(jobs, exist_ok=True)
    results = []
    for j in spec["jobs"]:
        stem = j["stem"]
        image = j["image"]
        if not os.path.isabs(image):
            image = os.path.join(WS, image)
        image = image.replace("\\", "/")
        machine = j.get("machine", "a3dtf1390")
        prs = j.get("prs", MACHINE_PRS.get(machine, "./A3-DTF-1390.prs"))
        out = os.path.join(prns, stem + ".prn").replace("\\", "/")
        job = O.build_job(
            image, prs, j.get("mode", 0), out,
            rotate=j.get("rotate", 0), scale=tuple(j.get("scale", (100, 100))),
            margin=tuple(j.get("margin", (0, 0, 0, 0))),
            mirror=j.get("mirror"), white=j.get("variant", "base"),
            ice=j.get("ice"), inkie=j.get("inkie"),
            dpi=tuple(j.get("dpi", (120, 120))), job_id=j.get("id"),
            extra=j.get("extra"))
        # run_job writes to O.JOBS; use explicit save paths when overridden
        t0 = time.time()
        job_path = os.path.join(jobs, stem + ".json")
        resp_path = os.path.join(jobs, stem + ".resp.json")
        with open(job_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(job, f, ensure_ascii=False, indent=2)
        resp = O.post(job, timeout=O.DEFAULT_TIMEOUT)
        with open(resp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(resp, f, ensure_ascii=False, indent=2)
        size = os.path.getsize(out) if os.path.isfile(out) else 0
        rec = {"stem": stem, "image": image, "machine": machine, "prs": prs,
               "mode": j.get("mode", 0), "variant": j.get("variant", "base"),
               "result": resp.get("result"), "error": resp.get("error"),
               "elapsed_s": resp.get("_elapsed_s", round(time.time() - t0, 3)),
               "prn": out, "job": job_path, "size": size}
        if size:
            rec["sha256"] = O.sha256_file(out)
            rec["sha256_norm"] = O.sha256_file(out, normalize=True)
            rec["format"] = ("hssf-0x5555" if open(out, "rb").read(2) == b"\x55\x55"
                             else "esc/p2")
        results.append(rec)
        print("%-28s result=%-3s size=%-10d t=%ss %s" %
              (stem, rec["result"], size, rec["elapsed_s"], rec.get("format", "")))
    return results


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--prn-dir", default=None)
    ap.add_argument("--jobs-dir", default=None)
    ap.add_argument("--summary", default=None)
    a = ap.parse_args(argv)
    with open(a.spec, "r", encoding="utf-8-sig") as f:
        spec = json.load(f)
    res = run_spec(spec, a.prn_dir, a.jobs_dir)
    summary = {"spec": a.spec, "n": len(res), "jobs": res}
    path = a.summary or os.path.join(HERE, "last_batch_summary.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("summary:", path)
    fails = [r for r in res if r["result"] != 0]
    print("failed: %d / %d" % (len(fails), len(res)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
