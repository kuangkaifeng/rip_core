#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""White-ink / transparency matrix on the alpha checker input.

Combines global `config color` (readTransparency / transparencyToWhite) with
the two ways of adding a white channel:
  * legacy  rip "whiteInk" array (adds channel AFTER halftone; works on mode2)
  * v2.14+  rip "inputColorEditor" W1 full (only yields output when the prs
            mode itself owns a W channel, i.e. A3 mode1/3, H13)
Output evidence: work/protocol/evidence/white_matrix.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "prn_tools"))
sys.path.insert(0, HERE)
import mtrip_oracle as O            # noqa: E402
from exp_params import prn_features  # noqa: E402

EV = os.path.join(HERE, "evidence")
A3 = "./A3-DTF-1390.prs"


def job_run(stem, mode, image, extra=None, variant="base", ice=None):
    out = os.path.join(O.PRNS, stem + ".prn").replace("\\", "/")
    img = os.path.join(WS, "reference", "inputs", image + ".png").replace("\\", "/")
    job = O.build_job(img, A3, mode, out, white=variant, ice=ice, extra=extra)
    r = O.run_job(job, stem)
    rec = {"stem": stem, "mode": mode, "image": image, "variant": variant,
           "extra": extra, "result": r["response"].get("result"),
           "prn": out}
    if r["prn_size"]:
        rec["features"] = prn_features(out)
    print("%-44s result=%s size=%-9s colors=%s" % (
        stem, rec["result"], r["prn_size"],
        {c: round(v["coverage"], 3) for c, v in
         rec.get("features", {}).get("colors", {}).items()}))
    return rec


def main():
    os.makedirs(EV, exist_ok=True)
    rows = []
    ic = lambda mode, ink="W1": [{"mode": mode, "invert": False, "inkName": ink}]
    # A. global config matrix, legacy whiteInk full/color/seperate on mode2
    for rt, tw in ((True, False), (True, True)):
        O.config("color", readTransparency=rt, transparencyToWhite=tw,
                 embeddedICC=True, cache=True)
        for wm in ("full", "color", "seperate"):
            rows.append(job_run(
                "exp_a3_white_matrix_legacy_%s_rt%d_tw%d" % (wm, rt, tw),
                2, "alpha_checker_100",
                extra={"whiteInk": [{"mode": wm, "density": "normal"}]}))
    # B. inputColorEditor W1 full on W-capable prs modes, rt true/tw false
    O.config("color", readTransparency=True, transparencyToWhite=False,
             embeddedICC=True, cache=True)
    for mode in (1, 3):
        rows.append(job_run("exp_a3_white_matrix_ice_m%d_alpha_rt1_tw0" % mode,
                            mode, "alpha_checker_100", ice=ic("full")))
    for mode in (1, 3):
        rows.append(job_run("exp_a3_white_matrix_ice_m%d_cmykquad_rt1_tw0" % mode,
                            mode, "cmyk_quad_100", ice=ic("full")))
    # C. transparencyToWhite on, inputColorEditor W1 full, mode3
    O.config("color", readTransparency=True, transparencyToWhite=True,
             embeddedICC=True, cache=True)
    rows.append(job_run("exp_a3_white_matrix_ice_m3_alpha_rt1_tw1",
                        3, "alpha_checker_100", ice=ic("full")))
    # restore observed default config of the restarted instance
    O.config("color", readTransparency=False, transparencyToWhite=False,
             embeddedICC=True, cache=True)
    with open(os.path.join(EV, "white_matrix.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("saved evidence/white_matrix.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
