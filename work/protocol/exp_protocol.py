#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operational / protocol experiments against mtripNet HTTP service.

Evidence is written into work/protocol/evidence/ as JSON/text.
Run:  set PYTHONIOENCODING=utf-8 && python exp_protocol.py
"""
import json
import os
import sys
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

EV = os.path.join(HERE, "evidence")
os.makedirs(EV, exist_ok=True)


def dump(name, obj):
    p = os.path.join(EV, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    print(f"  -> evidence/{name}")
    return p


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def byte_diff_summary(a, b):
    da = open(a, "rb").read()
    db = open(b, "rb").read()
    n = min(len(da), len(db))
    diffs = []
    i = 0
    while i < n:
        if da[i] != db[i]:
            j = i
            while j < n and da[j] != db[j]:
                j += 1
            diffs.append([i, j])
            i = j
        else:
            i += 1
    return {"len_a": len(da), "len_b": len(db), "n_ranges": len(diffs),
            "ranges": diffs[:20], "total_diff": sum(j - i for i, j in diffs)}


def main():
    out = {}
    # ---------- 1. queryMode with inks ----------
    print("[1] queryMode inks")
    qm = {}
    for key in ("a3dtf1390", "h13xp600"):
        r = O.query_mode(O.PRS[key], inks=True)
        qm[key] = r
    out["queryMode"] = qm
    dump("queryMode.json", qm)

    # ---------- 2. queryFile on generated inputs ----------
    print("[2] queryFile")
    qf = {}
    names = ["flat_black_100.png", "flat_white_100.png", "cmyk_quad_100.png",
             "alpha_checker_100.png", "alpha_grad_100.png", "checker_1px_100.png",
             "cmyk_quad_720.png", "flat_black_64.png"]
    for n in names:
        img = os.path.join(WS, "reference", "inputs", n).replace("\\", "/")
        qf[n] = O.post({"command": "queryFile", "doc": {"name": img}})
    out["queryFile"] = qf
    dump("queryFile.json", qf)

    # ---------- 3. determinism per machine ----------
    print("[3] determinism")
    det = {}
    for key, mode, white in (("a3dtf1390", 0, "none"), ("a3dtf1390", 2, "golden"),
                             ("h13xp600", 0, "none"), ("h13xp600", 1, "golden")):
        paths = []
        for i in (1, 2):
            tag = f"det_{key}_m{mode}_{white}_{i}"
            j = O.build_job("reference/inputs/flat_black_100.png", O.PRS[key], mode,
                            os.path.join(O.PRNS, tag + ".prn"), white=white)
            r = O.run_job(j, tag)
            paths.append(j["output"]["file"]["name"])
            det[tag] = {"result": r["response"].get("result"),
                        "size": r["prn_size"],
                        "sha256": sha(paths[-1]) if os.path.isfile(paths[-1]) else None,
                        "elapsed": r["response"].get("_elapsed_s")}
        det[f"{key}_m{mode}_{white}_diff"] = byte_diff_summary(paths[0], paths[1])
    out["determinism"] = det
    dump("determinism.json", det)

    # ---------- 4. query job progress state after a job with id ----------
    print("[4] job id + progress query")
    j = O.build_job("reference/inputs/flat_black_100.png", O.PRS["a3dtf1390"], 0,
                    os.path.join(O.PRNS, "det_jobid_777.prn"), job_id=777)
    r = O.run_job(j, "det_jobid_777")
    q = O.query("job", id=777)
    out["jobid"] = {"rip_response": r["response"], "query_job": q}
    dump("jobid.json", out["jobid"])

    # ---------- 5. config color / buffer / errorString round trip ----------
    print("[5] config round trips")
    cfg = {}
    cfg["color_before"] = O.query("color")
    cfg["set_cache_off"] = O.config("color", cache=False)
    cfg["color_after"] = O.query("color")
    cfg["errorString_off"] = O.config("errorString", setting=0)
    cfg["err_when_off"] = O.post({"command": "rip", "doc": {"name": "D:/nope_zzz.png"},
                                  "prs": "./A3-DTF-1390.prs", "modeId": 0,
                                  "output": {"mode": "file", "file": {"name": "D:/nope.prn"}}})
    cfg["errorString_on"] = O.config("errorString", setting=1)
    cfg["err_when_on"] = O.post({"command": "rip", "doc": {"name": "D:/nope_zzz.png"},
                                 "prs": "./A3-DTF-1390.prs", "modeId": 0,
                                 "output": {"mode": "file", "file": {"name": "D:/nope.prn"}}})
    cfg["buffer"] = O.query("buffer")
    cfg["opt"] = O.query("opt")
    # restore color config to the values observed before the experiment
    before = cfg["color_before"]
    cfg["color_restore"] = O.config(
        "color",
        embeddedICC=before.get("embeddedICC", True),
        cache=before.get("cache", True),
        transparencyToWhite=before.get("transparencyToWhite", False),
        readTransparency=before.get("readTransparency", False))
    cfg["color_after_restore"] = O.query("color")
    out["config"] = cfg
    dump("config.json", cfg)

    with open(os.path.join(EV, "protocol_summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
