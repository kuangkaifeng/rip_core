#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild a manifest over ALL files in reference/prn_samples/.

Scans every *.prn, finds the matching job JSON (reference/jobs/<stem>.json) and
response (reference/jobs/<stem>.resp.json), and writes
reference/jobs/manifest_all.csv sorted by stem.  Works offline.

Run: python tools/oracle/build_manifest.py
"""
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import mtrip_oracle as O   # noqa: E402

OUT = os.path.join(O.JOBS, "manifest_all.csv")
FIELDS = ["stem", "prn", "size", "format", "sha256", "sha256_norm",
          "job_json", "result", "elapsed_s", "prs", "modeId", "image",
          "params"]


def main():
    rows = []
    for prn in sorted(glob.glob(os.path.join(O.PRNS, "*.prn"))):
        stem = os.path.splitext(os.path.basename(prn))[0]
        size = os.path.getsize(prn)
        if size == 0:
            continue
        head = open(prn, "rb").read(2)
        fmt = "hssf-0x5555" if head == b"\x55\x55" else (
            "esc/p2" if head == b"\x00\x00" else "other")
        jp = os.path.join(O.JOBS, stem + ".json")
        rp = os.path.join(O.JOBS, stem + ".resp.json")
        job = {}
        try:
            job = json.load(open(jp, encoding="utf-8-sig"))
        except Exception:
            pass
        resp = {}
        try:
            resp = json.load(open(rp, encoding="utf-8-sig"))
        except Exception:
            pass
        params = {k: job[k] for k in
                  ("rotate", "scale", "margin", "mirror", "view", "dpi",
                   "inkIE", "inputColorEditor", "whiteInk", "color", "range", "id")
                  if k in job}
        rows.append({
            "stem": stem, "prn": prn, "size": size, "format": fmt,
            "sha256": O.sha256_file(prn),
            "sha256_norm": O.sha256_file(prn, normalize=True),
            "job_json": jp if os.path.isfile(jp) else "",
            "result": resp.get("result", ""),
            "elapsed_s": resp.get("_elapsed_s", ""),
            "prs": job.get("prs", ""),
            "modeId": job.get("modeId", ""),
            "image": job.get("doc", {}).get("name", ""),
            "params": json.dumps(params, ensure_ascii=False)})
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print("wrote %s (%d rows)" % (OUT, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
