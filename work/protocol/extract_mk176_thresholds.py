#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract T1/T2/T3 + exact D fields for M176/K176 and compare with the
complement relation to C176/Y176.

Outputs (same format as C176/Y176):
  work/protocol/evidence/probe_scan_thresholds_M176.bin / _K176.bin
  work/protocol/evidence/probe_scan_D_M176.bin / probe_scan_D_K176.bin
  work/protocol/evidence/probe_scan_D_MK176_summary.json   (incl. complement check)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))

import numpy as np

import extract_tile176_thresholds as EX   # generic extract(kind, ink)
import derive_D_tile176 as DD             # generic derive(kind)


def load_D(kind):
    path = os.path.join(EX.EV, "probe_scan_D_%s.bin" % kind)
    raw = open(path, "rb").read()
    return np.frombuffer(raw, dtype="<u2").copy()


def main():
    out = {"generated": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
           "note": "M176/K176 thresholds + exact D, plus complement check vs C176/Y176",
           "channels": {}}
    for kind, ink in (("M176", "M"), ("K176", "K")):
        out["channels"][ink] = EX.extract(kind, ink)
        out["channels"][ink].update(DD.derive(kind))
    # complement check on common page pixels (same 176 geometry => same raster layout)
    checks = {}
    for a, b in (("M176", "C176"), ("K176", "Y176")):
        Da = load_D(a)
        Db = load_D(b)
        m = (Da != 0xFFFF) & (Db != 0xFFFF)
        comp = (258 - Db[m].astype(np.int32)) & 0xFFFF
        same = int((Da[m].astype(np.int32) == comp).sum())
        checks["%s_vs_258-%s" % (a, b)] = {
            "pixels": int(m.sum()), "same": same,
            "same_pct": round(100.0 * same / max(1, int(m.sum())), 4),
            "different": int(m.sum()) - same,
        }
        print("%s vs 258-%s: %s" % (a, b, checks["%s_vs_258-%s" % (a, b)]))
    out["complement_check"] = checks
    p = os.path.join(EX.EV, "probe_scan_D_MK176_summary.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved", os.path.basename(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
