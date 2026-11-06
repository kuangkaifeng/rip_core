#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T9-B: A3-DTF-1390 white-ink oracle review.

Runs a compact matrix of A3 jobs (mode2 4-plane vs mode1/mode3 6-plane) and
records, per PRN, which ESC/P2 colour codes carry ink and how many dots — to
answer: does the A3 modified machine print white in PRN, with which API field,
and what does the production mode2+W1 job actually contain.

Outputs:
  reference/prn_samples/print_debug_white_*.prn
  reference/jobs/print_debug_white_*.json / .resp.json
  work/protocol/evidence/whiteink_a3.json
Sequential POST only.
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "prn_tools"))
import mtrip_oracle as O   # noqa: E402
import parse_prn as P      # noqa: E402

EV = os.path.join(HERE, "evidence")
PRS = "./A3-DTF-1390.prs"
ICE_W1_FULL = [{"mode": "full", "invert": False, "inkName": "W1"}]
ICE_W1_COLOR = [{"mode": "color", "invert": False, "inkName": "W1"}]
ICE_W2_FULL = [{"mode": "full", "invert": False, "inkName": "W2"}]
INKIE = [{"mode": "invaginate", "index": 4, "dots": [10, 10, 10, 10]}]


def prn_codes(path):
    job = P.parse_job(open(path, "rb").read(), decode=True)
    per = {}
    for b in job.blocks:
        for r in b.records:
            d = per.setdefault(r.color, {"ink": 0, "records": 0, "n": r.n, "m": r.m})
            d["records"] += 1
            if r.raw:
                d["ink"] += sum(1 for byte in r.raw for sh in (0, 2, 4, 6)
                                if (byte >> sh) & 3)
    return {"blocks": len(job.blocks),
            "colors": {"0x%02X" % c: d for c, d in sorted(per.items())}}


def run(case, image, mode, ice=None, inkie=None, extra=None):
    stem = "print_debug_white_" + case
    img = os.path.join(O.INPUTS, image).replace("\\", "/")
    out = os.path.join(O.PRNS, stem + ".prn").replace("\\", "/")
    job = O.build_job(img, PRS, mode, out, ice=ice, inkie=inkie, extra=extra)
    r = O.run_job(job, stem)
    rec = {"case": case, "image": image, "mode": mode,
           "ice": ice, "inkie": inkie, "extra": extra,
           "prn": out, "job": os.path.join(O.JOBS, stem + ".json"),
           "result": r["response"].get("result"),
           "error": r["response"].get("error"),
           "size": r["prn_size"]}
    if r["prn_size"]:
        rec["codes"] = prn_codes(out)
    print("%-46s mode=%d result=%s size=%-9s codes=%s" % (
        case, mode, rec["result"], r["prn_size"],
        {k: v["ink"] for k, v in (rec.get("codes") or {}).get("colors", {}).items()
         if v["ink"]}))
    return rec


def main():
    os.makedirs(EV, exist_ok=True)
    rows = []
    # A. 6-color mode3: single-channel CMYK TIFFs -> colour-code mapping
    for ink in ("C", "M", "Y", "K"):
        rows.append(run("m3_base_%s128" % ink, "cmyk_probe_%s128_64.tif" % ink, 3))
    # B. 6-color mode3: white generation
    rows.append(run("m3_iceW1full_black", "flat_black_100.png", 3, ice=ICE_W1_FULL))
    rows.append(run("m3_iceW2full_black", "flat_black_100.png", 3, ice=ICE_W2_FULL))
    rows.append(run("m3_iceW1full_alpha", "alpha_checker_100.png", 3, ice=ICE_W1_FULL))
    rows.append(run("m3_iceW1color_alpha", "alpha_checker_100.png", 3, ice=ICE_W1_COLOR))
    rows.append(run("m3_golden_quad", "cmyk_quad_100.png", 3,
                    ice=ICE_W1_FULL, inkie=INKIE))
    rows.append(run("m3_base_quad", "cmyk_quad_100.png", 3))
    # C. 6-color mode1 (720x360) equivalents
    for ink in ("C", "M", "Y", "K"):
        rows.append(run("m1_base_%s128" % ink, "cmyk_probe_%s128_64.tif" % ink, 1))
    rows.append(run("m1_iceW1full_black", "flat_black_100.png", 1, ice=ICE_W1_FULL))
    # D. 4-color mode2 controls: inputColorEditor vs legacy whiteInk
    rows.append(run("m2_iceW1full_black", "flat_black_100.png", 2, ice=ICE_W1_FULL))
    rows.append(run("m2_iceW1color_alpha", "alpha_checker_100.png", 2, ice=ICE_W1_COLOR))
    rows.append(run("m2_whiteInk_full_quad", "cmyk_quad_100.png", 2,
                    extra={"whiteInk": [{"mode": "full", "density": "normal"}]}))
    rows.append(run("m2_golden_quad", "cmyk_quad_100.png", 2,
                    ice=ICE_W1_FULL, inkie=INKIE))
    with open(os.path.join(EV, "whiteink_a3.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("\nsaved evidence/whiteink_a3.json (%d jobs, %d failed)"
          % (len(rows), sum(1 for r in rows if r.get("result") != 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
