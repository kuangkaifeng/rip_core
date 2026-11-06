#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remaining parameter experiments (crash-safe), run after the oracle restart.

Safer ordering: protocol variants -> mirror/view -> inkIE/ICE/whiteInk ->
transparency -> H13 -> custom `dpi` parameter LAST (it killed the previous
mtripNet instance on 2026-11-06 14:54:14).

Every job is wrapped: connection errors are recorded as {"result": "CONN_ERR"}
and a GET /status health probe decides whether to keep going.

Usage: python work/protocol/exp_params2.py [--phase all|safe|dpi]
"""
import argparse
import json
import os
import sys
import time
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, HERE)
import mtrip_oracle as O            # noqa: E402
from exp_params import prn_features  # noqa: E402

EV = os.path.join(HERE, "evidence")
A3, H13 = "a3dtf1390", "h13xp600"
PRS = {A3: "./A3-DTF-1390.prs", H13: O.PRS["h13xp600"]}


def health():
    try:
        r = O.get("/mtrip/v1/status")
        return r.get("result") == 0
    except Exception:
        return False


def run(name, machine, mode, image="cmyk_quad_100", variant="base",
        mutate=None, **kw):
    stem = "exp_%s_%s" % (machine, name)
    out = os.path.join(O.PRNS, stem + ".prn").replace("\\", "/")
    img = image if os.path.isabs(image) else \
        os.path.join(WS, "reference", "inputs", image + ".png").replace("\\", "/")
    job = O.build_job(img, PRS[machine], mode, out, white=variant, **kw)
    if mutate:
        mutate(job)
    rec = {"name": name, "stem": stem, "machine": machine, "mode": mode,
           "image": image, "variant": variant,
           "params": {k: v for k, v in kw.items()}}
    try:
        r = O.run_job(job, stem)
        rec.update(result=r["response"].get("result"),
                   error=r["response"].get("error"),
                   elapsed_s=r["response"].get("_elapsed_s"),
                   prn=out)
        if r["prn_size"]:
            rec["features"] = prn_features(out)
        print("%-46s result=%s size=%-9s" % (
            stem, rec["result"], rec.get("features", {}).get("size", "-")))
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        rec.update(result="CONN_ERR", error=repr(e), prn=out)
        print("%-46s CONNECTION ERROR %r" % (stem, e))
    rec["server_healthy_after"] = health()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="all", choices=["all", "safe", "dpi"])
    args = ap.parse_args()
    os.makedirs(EV, exist_ok=True)
    O.config("errorString", setting=1)          # enable error strings
    exps = []

    def add(*a, **kw):
        r = run(*a, **kw)
        exps.append(r)
        if not r.get("server_healthy_after"):
            print("!! oracle died after", r["stem"], "-- stopping phase")
            return False
        return True

    if args.phase in ("all", "safe"):
        T = "cmyk_quad_100"
        # ---- mirror with real JSON booleans (ints were silently ignored?) ----
        add("m2_mirror_h_bool", A3, 2, T, mirror=(True, False)) and \
            add("m2_mirror_v_bool", A3, 2, T, mirror=(False, True)) and \
            add("m2_mirror_hv_bool", A3, 2, T, mirror=(True, True))
        # ---- view / embedded-DPI interplay on image input ----
        def drop_view(job):
            job.pop("view", None)
        add("dpi72img_no_view", A3, 2, "cmyk_quad_100_dpi72", mutate=drop_view)
        add("dpi72img_view120", A3, 2, "cmyk_quad_100_dpi72", dpi=(120, 120))
        add("dpi72img_view72", A3, 2, "cmyk_quad_100_dpi72", dpi=(72, 72))
        add("dpi300img_view120", A3, 2, "cmyk_quad_100_dpi300", dpi=(120, 120))
        add("dpi300img_no_view", A3, 2, "cmyk_quad_100_dpi300", mutate=drop_view)
        # ---- inkIE ----
        add("m2_golden", A3, 2, T, variant="golden")
        add("m2_golden_inkIE_inv10", A3, 2, T, variant="golden",
            inkie=[{"mode": "invaginate", "index": 4, "dots": [10, 10, 10, 10]}])
        add("m2_golden_inkIE_exp10", A3, 2, T, variant="golden",
            inkie=[{"mode": "expand", "index": 4, "dots": [10, 10, 10, 10]}])
        add("m3_golden", A3, 3, T, variant="golden")
        add("m3_golden_inkIE_inv5", A3, 3, T, variant="golden",
            inkie=[{"mode": "invaginate", "index": 4, "dots": [5, 5, 5, 5]}])
        add("m3_golden_inkIE_exp10", A3, 3, T, variant="golden",
            inkie=[{"mode": "expand", "index": 4, "dots": [10, 10, 10, 10]}])
        add("m3_golden_inkIE_W2_inv10", A3, 3, T, variant="golden",
            inkie=[{"mode": "invaginate", "index": 5, "dots": [10, 10, 10, 10]}])
        # ---- inputColorEditor modes ----
        for m in ("color", "smooth", "smoothNeg", "white", "whiteNeg"):
            add("ice_%s" % m, A3, 2, T,
                ice=[{"mode": m, "invert": False, "inkName": "W1"}])
        add("ice_full_invert", A3, 2, T,
            ice=[{"mode": "full", "invert": True, "inkName": "W1"}])
        add("ice_cmykw1w2", A3, 2, T,
            ice=[{"mode": "full", "invert": False, "inkName": "CMYKW1W2"}])
        # ---- legacy whiteInk parameter ----
        add("whiteInk_full_normal", A3, 2, T,
            extra={"whiteInk": [{"mode": "full", "density": "normal"}]})
        add("whiteInk_sep_ownset90", A3, 2, T,
            extra={"whiteInk": [{"mode": "seperate", "density": "ownset",
                                 "densityValue": 90}]})
        add("whiteInk_color_more", A3, 2, T,
            extra={"whiteInk": [{"mode": "color", "density": "more"}]})
        # ---- transparency handling (alpha checker + W1 golden) ----
        for rt, tw in ((True, False), (False, False), (True, True), (False, True)):
            add("alpha_rt%d_tw%d" % (rt, tw), A3, 2, "alpha_checker_100",
                variant="golden",
                color={"readTransparency": rt, "transparencyToWhite": tw})
        # ---- H13 board machine ----
        add("h13_rot180", H13, 0, T, rotate=180)
        add("h13_scale50", H13, 0, T, scale=(50, 50))
        add("h13_golden", H13, 0, T, variant="golden")
        add("h13_golden_inkIE_inv10", H13, 0, T, variant="golden",
            inkie=[{"mode": "invaginate", "index": 4, "dots": [10, 10, 10, 10]}])
        # ---- protocol variants ----
        def doctype(job):
            job["doc"]["type"] = "auto"
            job["doc"]["imageBufferSize"] = 1073741824
        add("doctype_auto", A3, 2, T, mutate=doctype)
        def no_extras(job):
            job.pop("range", None); job.pop("color", None); job.pop("view", None)
        add("no_range_no_color_no_view", A3, 2, T, mutate=no_extras)

    if args.phase in ("all", "dpi"):
        print("=== custom dpi parameter (previous instance died here) ===")
        if add("dpi_300_custom", A3, 2, "cmyk_quad_100",
               extra={"dpi": {"xdpi": 300, "ydpi": 300}}):
            add("dpi_1440x720_custom", A3, 2, "cmyk_quad_100",
                extra={"dpi": {"xdpi": 1440, "ydpi": 720}})

    with open(os.path.join(EV, "exp_params2.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(exps, f, ensure_ascii=False, indent=2)
    print("\nsaved evidence/exp_params2.json (%d rows)" % len(exps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
