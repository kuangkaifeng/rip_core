#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Key parameter experiments: job parameter -> PRN feature mapping.

Uses the mtripNet HTTP oracle (tools/oracle/mtrip_oracle.py) and T2's ESC/P2
parser (tools/prn_tools/parse_prn.py, read-only import) to measure how
modeId / rotate / scale / margin / mirror / view-dpi / custom-dpi / inkIE /
inputColorEditor / white-ink / transparency parameters change the PRN.

Outputs:
  reference/prn_samples/exp_*.prn           generated PRNs
  reference/jobs/exp_*.json                 the exact job JSON + response
  work/protocol/evidence/exp_params.json    measured feature table
  work/protocol/evidence/exp_errors.json    error-code behaviour probes

Run sequentially AFTER make_corpus.py finished (single oracle client at a time).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "prn_tools"))
import mtrip_oracle as O            # noqa: E402

EV = os.path.join(HERE, "evidence")
PARSER_DIR = os.path.join(WS, "tools", "prn_tools")
A3 = "a3dtf1390"
H13 = "h13xp600"

# ---------------------------------------------------------------------------
def prn_features(path):
    """Format + structure features.  ESC/P2 is parsed with T2's parser;
    HSSF 0x5555 only gets size/hash (format owned by T4)."""
    feat = {"size": os.path.getsize(path),
            "sha256": O.sha256_file(path),
            "sha256_norm": O.sha256_file(path, normalize=True)}
    head = open(path, "rb").read(8)
    if head[:2] == b"\x55\x55":
        feat["format"] = "hssf-0x5555"
        return feat
    try:
        import parse_prn as P
    except Exception as e:       # parser under development by T2
        feat["format"] = "esc-p2 (parser unavailable: %r)" % e
        return feat
    job = P.parse_job(open(path, "rb").read(), decode=True)
    pm = P.prologue_map(job)
    feat["format"] = "esc/p2"
    feat["epl"] = {
        "ESC_D": pm.get("ESC_D"), "ESC_S": pm.get("ESC_S"),
        "ESC_c": pm.get("ESC_c"), "ESC_m": pm.get("ESC_m"),
        "ESC_e": pm.get("ESC_e"), "ESC_K": pm.get("ESC_K"),
    }
    feat["blocks"] = len(job.blocks)
    feat["records"] = sum(len(b.records) for b in job.blocks)
    per = {}
    advances = sorted(set(b.advance for b in job.blocks if b.advance is not None))
    feat["advances"] = advances[:8]
    feat["advance_sum"] = sum(b.advance for b in job.blocks if b.advance is not None)
    xs = sorted(set(r.xpos for b in job.blocks for r in b.records))
    feat["xpos"] = xs[:8]
    for b in job.blocks:
        for r in b.records:
            d = per.setdefault(r.color, {"records": 0, "n": set(), "m": set(),
                                         "ink_px": 0, "total_px": 0})
            d["records"] += 1
            d["n"].add(r.n)
            d["m"].add(r.m)
            if r.raw:
                ink = 0
                for byte in r.raw:
                    ink += (1 if (byte & 3) else 0)
                    ink += (1 if (byte >> 2) & 3 else 0)
                    ink += (1 if (byte >> 4) & 3 else 0)
                    ink += (1 if (byte >> 6) & 3 else 0)
                d["ink_px"] += ink
            d["total_px"] += r.n * 4 * r.m
    feat["colors"] = {
        "0x%02X" % c: {"records": d["records"], "n": sorted(d["n"]),
                       "m": sorted(d["m"]), "ink_px": d["ink_px"],
                       "total_px": d["total_px"],
                       "coverage": round(d["ink_px"] / d["total_px"], 6) if d["total_px"] else 0}
        for c, d in sorted(per.items())}
    if job.warnings:
        feat["warnings"] = job.warnings[:6]
    return feat


def run(name, machine, mode, image="cmyk_quad_100", variant="base", **kw):
    """Run one experiment job and return feature dict."""
    stem = "exp_%s_%s" % (machine, name)
    out = os.path.join(O.PRNS, stem + ".prn").replace("\\", "/")
    img = os.path.join(WS, "reference", "inputs", image + ".png").replace("\\", "/")
    job = O.build_job(img, O.MACHINES_PRS[machine], mode, out, white=variant, **kw)
    r = O.run_job(job, stem)
    rec = {"name": name, "stem": stem, "machine": machine, "mode": mode,
           "image": image, "variant": variant, "params": {k: v for k, v in kw.items()},
           "result": r["response"].get("result"),
           "error": r["response"].get("error"),
           "elapsed_s": r["response"].get("_elapsed_s"),
           "prn": out}
    if r["prn_size"]:
        rec["features"] = prn_features(out)
    print("%-42s result=%s size=%-9s %s" % (
        stem, rec["result"], rec["features"]["size"] if rec.get("features") else "-",
        ("coverage=" + str({c: f["coverage"] for c, f in
                            rec["features"].get("colors", {}).items()})) if rec.get("features") else ""))
    return rec


def main():
    os.makedirs(EV, exist_ok=True)
    O.MACHINES_PRS = {A3: "./A3-DTF-1390.prs", H13: O.PRS["h13xp600"]}
    exps = []

    def add(**kw):
        exps.append(run(**kw))

    T = "cmyk_quad_100"
    # ---- A. rotate (mode 2: 720x720 CMYK) ----
    for deg in (90, 180, 270):
        add(name="rot%d" % deg, machine=A3, mode=2, image=T, rotate=deg)
    # ---- B. scale ----
    add(name="scale50", machine=A3, mode=2, image=T, scale=(50, 50))
    add(name="scale200", machine=A3, mode=2, image=T, scale=(200, 200))
    add(name="scale_100x50", machine=A3, mode=2, image=T, scale=(100, 50))
    add(name="scale_50x100", machine=A3, mode=2, image=T, scale=(50, 100))
    # ---- C. margin (left,top,right,bottom in mm) ----
    add(name="margin_5_10_15_20", machine=A3, mode=2, image=T, margin=(5, 10, 15, 20))
    # ---- D. mirror ----
    add(name="mirror_h", machine=A3, mode=2, image=T, mirror=(1, 0))
    add(name="mirror_v", machine=A3, mode=2, image=T, mirror=(0, 1))
    add(name="mirror_hv", machine=A3, mode=2, image=T, mirror=(1, 1))
    # ---- E. view dpi / custom dpi ----
    add(name="view_300", machine=A3, mode=2, image=T, dpi=(300, 300))
    add(name="view_600", machine=A3, mode=2, image=T, dpi=(600, 600))
    add(name="dpi_300", machine=A3, mode=2, image=T,
        extra={"dpi": {"xdpi": 300, "ydpi": 300}})
    add(name="dpi_1440x720", machine=A3, mode=2, image=T,
        extra={"dpi": {"xdpi": 1440, "ydpi": 720}})
    # ---- F. inkIE (mode 2 + golden W1 channel, and mode 3 W1W2) ----
    add(name="m2_golden", machine=A3, mode=2, image=T, variant="golden")
    add(name="m2_golden_inkIE_inv10", machine=A3, mode=2, image=T, variant="golden",
        inkie=[{"mode": "invaginate", "index": 4, "dots": [10, 10, 10, 10]}])
    add(name="m2_golden_inkIE_exp10", machine=A3, mode=2, image=T, variant="golden",
        inkie=[{"mode": "expand", "index": 4, "dots": [10, 10, 10, 10]}])
    add(name="m3_golden", machine=A3, mode=3, image=T, variant="golden")
    add(name="m3_golden_inkIE_inv5", machine=A3, mode=3, image=T, variant="golden",
        inkie=[{"mode": "invaginate", "index": 4, "dots": [5, 5, 5, 5]}])
    add(name="m3_golden_inkIE_exp10", machine=A3, mode=3, image=T, variant="golden",
        inkie=[{"mode": "expand", "index": 4, "dots": [10, 10, 10, 10]}])
    add(name="m3_golden_inkIE_W2_inv10", machine=A3, mode=3, image=T, variant="golden",
        inkie=[{"mode": "invaginate", "index": 5, "dots": [10, 10, 10, 10]}])
    # ---- G. inputColorEditor modes (mode 2, adds W1 channel) ----
    for m in ("color", "smooth", "smoothNeg", "white", "whiteNeg"):
        add(name="ice_%s" % m, machine=A3, mode=2, image=T,
            ice=[{"mode": m, "invert": False, "inkName": "W1"}])
    add(name="ice_full_invert", machine=A3, mode=2, image=T,
        ice=[{"mode": "full", "invert": True, "inkName": "W1"}])
    add(name="ice_cmykw1w2", machine=A3, mode=2, image=T,
        ice=[{"mode": "full", "invert": False, "inkName": "CMYKW1W2"}])
    # ---- H. legacy whiteInk command parameter ----
    add(name="whiteInk_full_normal", machine=A3, mode=2, image=T,
        extra={"whiteInk": [{"mode": "full", "density": "normal"}]})
    add(name="whiteInk_sep_ownset90", machine=A3, mode=2, image=T,
        extra={"whiteInk": [{"mode": "seperate", "density": "ownset", "densityValue": 90}]})
    add(name="whiteInk_color_more", machine=A3, mode=2, image=T,
        extra={"whiteInk": [{"mode": "color", "density": "more"}]})
    # ---- I. transparency handling on alpha_checker (W1 golden) ----
    add(name="alpha_rt1_tw0", machine=A3, mode=2, image="alpha_checker_100", variant="golden",
        color={"readTransparency": True, "transparencyToWhite": False})
    add(name="alpha_rt0_tw0", machine=A3, mode=2, image="alpha_checker_100", variant="golden",
        color={"readTransparency": False, "transparencyToWhite": False})
    add(name="alpha_rt1_tw1", machine=A3, mode=2, image="alpha_checker_100", variant="golden",
        color={"readTransparency": True, "transparencyToWhite": True})
    add(name="alpha_rt0_tw1", machine=A3, mode=2, image="alpha_checker_100", variant="golden",
        color={"readTransparency": False, "transparencyToWhite": True})
    # ---- J. H13 board machine parameter response ----
    add(name="h13_rot180", machine=H13, mode=0, image=T, rotate=180)
    add(name="h13_scale50", machine=H13, mode=0, image=T, scale=(50, 50))
    add(name="h13_golden", machine=H13, mode=0, image=T, variant="golden")
    add(name="h13_golden_inkIE_inv10", machine=H13, mode=0, image=T, variant="golden",
        inkie=[{"mode": "invaginate", "index": 4, "dots": [10, 10, 10, 10]}])
    # ---- K. protocol variants: explicit doc.type, no range, no color ----
    out = os.path.join(O.PRNS, "exp_a3_doctype_auto.prn").replace("\\", "/")
    j = O.build_job("reference/inputs/cmyk_quad_100.png", "./A3-DTF-1390.prs", 2, out)
    j["doc"]["type"] = "auto"; j["doc"]["imageBufferSize"] = 1073741824
    r = O.run_job(j, "exp_a3_doctype_auto")
    exps.append({"name": "doctype_auto", "stem": "exp_a3_doctype_auto",
                 "result": r["response"].get("result"), "prn": out,
                 "features": prn_features(out) if r["prn_size"] else None})
    out = os.path.join(O.PRNS, "exp_a3_no_range_no_color.prn").replace("\\", "/")
    j = O.build_job("reference/inputs/cmyk_quad_100.png", "./A3-DTF-1390.prs", 2, out)
    j.pop("range", None); j.pop("color", None); j.pop("view", None)
    r = O.run_job(j, "exp_a3_no_range_no_color")
    exps.append({"name": "no_range_no_color_no_view", "stem": "exp_a3_no_range_no_color",
                 "result": r["response"].get("result"), "prn": out,
                 "features": prn_features(out) if r["prn_size"] else None})

    with open(os.path.join(EV, "exp_params.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(exps, f, ensure_ascii=False, indent=2)
    print("\nsaved evidence/exp_params.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
