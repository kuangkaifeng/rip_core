#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline feature extraction for already-generated experiment PRNs.

Does NOT touch mtripNet: reads reference/prn_samples/exp_*.prn + the job JSON in
reference/jobs/ and derives the parameter->PRN feature table.  Safe to run while
the oracle is down.

Output: work/protocol/evidence/exp_features.json (+ printed table).
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O            # noqa: E402

EV = os.path.join(HERE, "evidence")
PARSER_DIR = os.path.join(WS, "tools", "prn_tools")
sys.path.insert(0, PARSER_DIR)


def features(path):
    f = {"size": os.path.getsize(path)}
    if not f["size"]:
        return f
    f["sha256"] = O.sha256_file(path)
    f["sha256_norm"] = O.sha256_file(path, normalize=True)
    head = open(path, "rb").read(8)
    if head[:2] == b"\x55\x55":
        f["format"] = "hssf-0x5555"
        return f
    f["format"] = "esc/p2"
    try:
        import parse_prn as P
        job = P.parse_job(open(path, "rb").read(), decode=True)
        pm = P.prologue_map(job)
        f["ESC_D"] = pm.get("ESC_D")
        f["ESC_S"] = pm.get("ESC_S")
        f["ESC_c"] = pm.get("ESC_c")
        f["ESC_m"] = pm.get("ESC_m")
        f["ESC_e"] = pm.get("ESC_e")
        f["blocks"] = len(job.blocks)
        f["advances"] = sorted(set(b.advance for b in job.blocks if b.advance))
        f["advance_sum"] = sum(b.advance for b in job.blocks if b.advance)
        per = {}
        for b in job.blocks:
            for r in b.records:
                d = per.setdefault(r.color, {"records": 0, "n": set(), "m": set(),
                                             "ink": 0, "total": 0})
                d["records"] += 1
                d["n"].add(r.n)
                d["m"].add(r.m)
                if r.raw:
                    ink = 0
                    for byte in r.raw:
                        ink += (1 if (byte & 3) else 0) + (1 if (byte >> 2) & 3 else 0) \
                             + (1 if (byte >> 4) & 3 else 0) + (1 if (byte >> 6) & 3 else 0)
                    d["ink"] += ink
                d["total"] += r.n * 4 * r.m
        f["colors"] = {"0x%02X" % c: {"records": d["records"], "n": sorted(d["n"]),
                                      "m": sorted(d["m"]), "ink_px": d["ink"],
                                      "total_px": d["total"],
                                      "coverage": round(d["ink"] / d["total"], 6) if d["total"] else 0}
                       for c, d in sorted(per.items())}
    except Exception as e:
        f["parse_error"] = repr(e)
    return f


def job_params(job_path):
    try:
        j = json.load(open(job_path, encoding="utf-8-sig"))
    except Exception:
        return {}
    keep = ["modeId", "rotate", "scale", "margin", "mirror", "view", "dpi",
            "inkIE", "inputColorEditor", "whiteInk", "color", "range", "id"]
    return {k: j[k] for k in keep if k in j}


def main():
    rows = []
    for prn in sorted(glob.glob(os.path.join(O.PRNS, "exp_*.prn"))):
        stem = os.path.splitext(os.path.basename(prn))[0]
        jp = os.path.join(O.JOBS, stem + ".json")
        resp = os.path.join(O.JOBS, stem + ".resp.json")
        row = {"stem": stem, "prn": prn,
               "mode": job_params(jp).get("modeId"),
               "params": job_params(jp),
               "features": features(prn)}
        if os.path.isfile(resp):
            try:
                row["response"] = json.load(open(resp, encoding="utf-8-sig"))
            except Exception:
                pass
        rows.append(row)
        f = row["features"]
        print("%-46s size=%-9d blocks=%-4s adv=%-26s cov=%s" % (
            stem, f["size"], f.get("blocks"),
            str(f.get("advances"))[:26],
            {c: round(v["coverage"], 4) for c, v in f.get("colors", {}).items()}))
    os.makedirs(EV, exist_ok=True)
    with open(os.path.join(EV, "exp_features.json"), "w", encoding="utf-8", newline="\n") as fp:
        json.dump(rows, fp, ensure_ascii=False, indent=2)
    print("\nsaved evidence/exp_features.json (%d rows)" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
