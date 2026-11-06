#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-ink/value solid patches WITHOUT mtcount (mtcount is rejected by this
driver: instant {"result":1,"error":"用户取消"}).

Each image contains exactly one ink at a known value, so the generated PRN's
per-color-code raster directly measures the halftone/linearization response for
that input level.  Runs A3-DTF-1390 modeId=2 and modeId=0.

Evidence: work/protocol/evidence/screen_probe_singles.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

EV = os.path.join(HERE, "evidence")
INK_LEVELS = [(ink, v) for ink in ("C", "M", "Y", "K")
              for v in (0, 64, 128, 192, 255)]


def main():
    rows = []
    for ink, v in INK_LEVELS:
        fn = "cmyk_probe_%s%d_64.tif" % (ink, v)
        case = "probe_%s%d" % (ink, v)
        for mode in (2, 0):
            stem = "probe_screen_%s_a3dtf1390_m%d" % (case, mode)
            img = os.path.join(O.INPUTS, fn).replace("\\", "/")
            out = os.path.join(O.PRNS, stem + ".prn").replace("\\", "/")
            job = O.build_job(img, "./A3-DTF-1390.prs", mode, out)
            r = O.run_job(job, stem)
            rec = {"stem": stem, "ink": ink, "value": v, "mode": mode,
                   "image": fn, "result": r["response"].get("result"),
                   "error": r["response"].get("error"),
                   "prn": out, "size": r["prn_size"]}
            rows.append(rec)
            print("%-46s ink=%s v=%-3d result=%s size=%s" % (
                stem, ink, v, rec["result"], rec["size"]))
    with open(os.path.join(EV, "screen_probe_singles.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    bad = [r for r in rows if r["result"] != 0]
    print("\nsaved (%d rows, %d failed)" % (len(rows), len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
