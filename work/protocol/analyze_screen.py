#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T6-B analysis: decode the screening probe PRNs with T2's ESC/P2 parser and
extract per-color-code ink coverage + 2-bit dot-size histograms.

Evidence: work/protocol/evidence/screen_probe_features.json
Also prints tables used by work/protocol/screen_probe.md.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "prn_tools"))
import mtrip_oracle as O   # noqa: E402

EV = os.path.join(HERE, "evidence")


def esc_features(path):
    """Return {format, blocks, colors:{code:{records,n,m,ink,total,hist,coverage}}}."""
    data = open(path, "rb").read()
    f = {"size": len(data), "sha256": O.sha256_file(path),
         "sha256_norm": O.sha256_file(path, normalize=True)}
    if data[:2] == b"\x55\x55":
        f["format"] = "hssf-0x5555"
        return f
    f["format"] = "esc/p2"
    import parse_prn as P
    job = P.parse_job(data, decode=True)
    f["blocks"] = len(job.blocks)
    per = {}
    for b in job.blocks:
        for r in b.records:
            d = per.setdefault(r.color, {"records": 0, "n": set(), "m": set(),
                                         "ink": 0, "total": 0,
                                         "hist": {1: 0, 2: 0, 3: 0}})
            d["records"] += 1
            d["n"].add(r.n)
            d["m"].add(r.m)
            if r.raw:
                for byte in r.raw:
                    for sh in (0, 2, 4, 6):
                        v = (byte >> sh) & 3
                        if v:
                            d["ink"] += 1
                            d["hist"][v] += 1
            d["total"] += r.n * 4 * r.m
    f["colors"] = {
        "0x%02X" % c: {"records": d["records"], "n": sorted(d["n"]),
                       "m": sorted(d["m"]), "ink_px": d["ink"],
                       "total_px": d["total"],
                       "hist": {"%d" % k: v for k, v in d["hist"].items()},
                       "coverage": round(d["ink"] / d["total"], 6) if d["total"] else 0}
        for c, d in sorted(per.items())}
    return f


def main():
    out = []
    for prn in sorted(glob.glob(os.path.join(O.PRNS, "probe_screen_*.prn"))):
        stem = os.path.basename(prn)[:-4]
        if os.path.getsize(prn) == 0:
            continue
        try:
            f = esc_features(prn)
        except Exception as e:
            f = {"size": os.path.getsize(prn), "error": repr(e)}
        rec = {"stem": stem, "prn": prn, "features": f}
        out.append(rec)
        cols = f.get("colors", {})
        brief = " ".join("%s:cov=%.4f" % (c, v["coverage"]) for c, v in cols.items())
        print("%-50s %-10s %s" % (stem, f.get("format"), brief))
    with open(os.path.join(EV, "screen_probe_features.json"), "w",
              encoding="utf-8", newline="\n") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    print("\nsaved evidence/screen_probe_features.json (%d)" % len(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
