#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Global `config color` semantics + error-code protocol probes.

Covers:
  * config/color readTransparency + transparencyToWhite effects on an alpha PNG
    (per-job "color" object vs global config -- earlier 4 per-job variants were
    byte-identical, so this isolates whether color is applied globally only)
  * error-code behaviour for bad doc/prs/modeId/output/command
  * restore config color to the observed defaults afterwards

Run after exp_params2 --phase safe; writes evidence/config_color_tx.json,
evidence/errors.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

EV = os.path.join(HERE, "evidence")
A3 = "./A3-DTF-1390.prs"


def run(name, **job_kw):
    out = os.path.join(O.PRNS, "exp_a3_" + name + ".prn").replace("\\", "/")
    image = job_kw.pop("image", "reference/inputs/alpha_checker_100.png")
    mode = job_kw.pop("mode", 2)
    white = job_kw.pop("variant", "base")
    job = O.build_job(image, A3, mode, out, white=white, **job_kw)
    try:
        r = O.run_job(job, "exp_a3_" + name)
        print("%-42s result=%s size=%s" % (name, r["response"].get("result"), r["prn_size"]))
        return {"name": name, "result": r["response"].get("result"),
                "size": r["prn_size"],
                "sha_norm": O.sha256_file(out, normalize=True) if r["prn_size"] else None,
                "job": job}
    except Exception as e:
        print("%-42s ERROR %r" % (name, e))
        return {"name": name, "error": repr(e)}


def main():
    res = {}
    before = O.query("color")
    res["color_before"] = before
    cases = []
    for rt, tw in ((True, False), (False, False), (True, True), (False, True), (True, False)):
        res["config_color_rt%d_tw%d" % (rt, tw)] = O.config(
            "color", readTransparency=rt, transparencyToWhite=tw,
            embeddedICC=True, cache=True)
        cases.append(run("tx_rt%d_tw%d" % (rt, tw), variant="golden"))
    res["transparency_runs"] = cases
    # restore
    res["config_color_restore"] = O.config(
        "color", readTransparency=before.get("readTransparency", False),
        transparencyToWhite=before.get("transparencyToWhite", False),
        embeddedICC=before.get("embeddedICC", True), cache=True)
    res["color_after"] = O.query("color")

    # ---------- error code probes ----------
    errs = {}

    def probe(name, job):
        try:
            r = O.post(job, timeout=120)
        except Exception as e:
            r = {"_exception": repr(e)}
        errs[name] = r
        print("%-32s -> %s" % (name, json.dumps(r, ensure_ascii=False)))

    base = O.build_job("reference/inputs/flat_black_100.png", A3, 2,
                       os.path.join(O.PRNS, "err_probe.prn"))
    j = json.loads(json.dumps(base)); j["doc"]["name"] = "D:/no_such_image_zzz.png"
    probe("missing_input_file", j)
    j = json.loads(json.dumps(base)); j["prs"] = "D:/no_such_prs_zzz.prs"
    probe("missing_prs", j)
    j = json.loads(json.dumps(base)); j["modeId"] = 99
    probe("bad_modeId_99", j)
    j = json.loads(json.dumps(base)); j["modeId"] = -1
    probe("bad_modeId_neg1", j)
    j = json.loads(json.dumps(base))
    j["output"]["file"]["name"] = "D:/work/RIP核心分析/reference/no_such_dir_zzz/x.prn"
    probe("bad_output_dir", j)
    probe("unknown_command", {"command": "bogus"})
    probe("bad_json_type", {"command": 1})
    probe("no_command", {"doc": {"name": "x"}})
    j = json.loads(json.dumps(base)); j["doc"]["name"] = "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/A3-DTF-1390.prs"
    probe("prs_as_input_image", j)
    # explicit type mismatch
    j = json.loads(json.dumps(base)); j["doc"]["type"] = "pdf"
    probe("doc_type_pdf_on_png", j)
    res["errors"] = errs

    os.makedirs(EV, exist_ok=True)
    with open(os.path.join(EV, "config_color_tx.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("saved evidence/config_color_tx.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
