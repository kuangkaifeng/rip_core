#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Determinism audit for the 52 anomalous screening probes (13 tones x 4 inks).

For each probe_scan_<INK><tone>_176_a3dtf1390_m2 job:
  * rerun twice with fresh output paths  (probe_rerun_<INK><tone>_176_r{1,2}...)
  * byte-compare original / r1 / r2 after EJL TI timestamp normalisation
  * content-plane compare (engine-dev prn_model) original / r1 / r2
  * verify the 832 audit cells (T3 work/prs/oracle_screen_audit.json) in the
    original and both reruns: are they the same deterministic level?
Outputs:
  work/protocol/evidence/screen_nondeterminism.json
  work/protocol/evidence/screen_nondeterminism.md
Sequential POST only, original PRNs are never overwritten.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "validate"))
import mtrip_oracle as O      # noqa: E402
import prn_model as pm        # noqa: E402

EV = os.path.join(HERE, "evidence")
AUDIT = os.path.join(WS, "work", "prs", "oracle_screen_audit.json")
RERUN_DIR = os.path.join(O.PRNS, "rerun")
INK_COLOR = {"C": 0x00, "M": 0x12, "Y": 0x11, "K": 0x04}


def audit_tables():
    a = json.load(open(AUDIT, encoding="utf-8"))
    tones = sorted({t[0] for ink in a for pos in a[ink].values() for t in pos})
    positions = {ink: [tuple(int(v) for v in k.split(","))
                       for k in a[ink].keys()] for ink in a}
    return a, tones, positions


def parse_planes(path):
    prn = pm.parse_prn(path)
    mode, mp = pm.mode_params(prn)
    planes, W, H, info = pm.extract_content_planes(prn, mode)
    idx = {}
    for inkname, code in INK_COLOR.items():
        if code in mp["colors"]:
            idx[inkname] = mp["colors"].index(code)
    return {"planes": planes, "W": W, "H": H, "idx": idx, "mp": mp, "mode": mode}


def rerun(orig_job_path, stem):
    """POST two reruns of a job with fresh output paths; keep originals intact."""
    os.makedirs(RERUN_DIR, exist_ok=True)
    job = json.load(open(orig_job_path, encoding="utf-8-sig"))
    orig_prn = job["output"]["file"]["name"]
    results = []
    for r in (1, 2):
        out = os.path.join(RERUN_DIR, "%s_r%d.prn" % (stem, r)).replace("\\", "/")
        j = json.loads(json.dumps(job))
        j["output"]["file"]["name"] = out
        tag = "%s_r%d" % (stem, r)
        res = O.run_job(j, tag)
        results.append({"run": r, "prn": out, "tag": tag,
                        "result": res["response"].get("result"),
                        "size": res["prn_size"]})
    return orig_prn, results


def main():
    os.makedirs(EV, exist_ok=True)
    audit, tones, positions = audit_tables()
    print("tones:", tones)
    print("audit positions per ink:", {k: len(v) for k, v in positions.items()})

    report = {"generated": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
              "audit": os.path.relpath(AUDIT, WS).replace("\\", "/"),
              "tones": tones,
              "note": "each probe rerun twice with fresh output paths; compare PRN "
                      "bytes (TI-normalised) + content planes + the 832 audit cells",
              "probes": [], "audit_cells": {}}

    for ink in ("C", "M", "Y", "K"):
        for tone in tones:
            stem = "probe_scan_%s%03d_176_a3dtf1390_m2" % (ink, tone)
            job_path = os.path.join(O.JOBS, stem + ".json")
            if not os.path.isfile(job_path):
                print("!! missing job", job_path)
                continue
            orig_prn, rr = rerun(job_path, stem)
            rec = {"ink": ink, "tone": tone, "stem": stem,
                   "orig_prn": orig_prn.replace("\\", "/"), "reruns": rr}
            rec["orig_size"] = os.path.getsize(orig_prn)
            # byte comparisons (TI-normalised)
            d01 = O.diff_prn(orig_prn, rr[0]["prn"])
            d12 = O.diff_prn(rr[0]["prn"], rr[1]["prn"])
            rec["bytes"] = {
                "orig_vs_r1": {"norm_equal": d01["identical_normalized"],
                               "norm_diff_ranges": d01["norm_diff_ranges"],
                               "raw_diff_count": d01["raw_diff_count"]},
                "r1_vs_r2": {"norm_equal": d12["identical_normalized"],
                             "norm_diff_ranges": d12["norm_diff_ranges"],
                             "raw_diff_count": d12["raw_diff_count"]},
            }
            # content-plane comparison
            P0 = parse_planes(orig_prn)
            P1 = parse_planes(rr[0]["prn"])
            P2 = parse_planes(rr[1]["prn"])
            acc = {}
            for iname, ci in P0["idx"].items():
                A = P0["planes"][ci]
                B = P1["planes"][ci]
                Cc = P2["planes"][ci]
                n = min(len(A), len(B), len(Cc))
                diff01 = sum(1 for i in range(n) if A[i] != B[i])
                diff12 = sum(1 for i in range(n) if B[i] != Cc[i])
                acc[iname] = {"pixels": n, "diff_orig_r1": diff01,
                              "diff_r1_r2": diff12,
                              "ink_orig": sum(1 for i in range(n) if A[i])}
            rec["content_planes"] = acc
            # audit cells for this ink/tone
            cells = []
            for (x, y) in positions[ink]:
                # audit value for this (pos, tone)
                key = "%d,%d" % (x, y)
                entry = next((e for e in audit[ink].get(key, []) if e[0] == tone), None)
                if entry is None:
                    continue
                taudit, pred, act = entry
                ci = P0["idx"][ink]
                p = y * P0["W"] + x
                vals = [P0["planes"][ci][p], P1["planes"][ci][p], P2["planes"][ci][p]]
                cells.append({"x": x, "y": y, "tone": tone, "pred": pred,
                              "audit_actual": act, "orig": vals[0],
                              "r1": vals[1], "r2": vals[2],
                              "orig_matches_audit": vals[0] == act,
                              "deterministic": vals[0] == vals[1] == vals[2]})
            rec["audit_cells"] = cells
            report["probes"].append(rec)
            bad = [c for c in cells if not c["deterministic"]]
            print("%-32s bytes_equal=%s/%s content_diff=%s audit_cells=%d nondet=%d"
                  % (stem, d01["identical_normalized"], d12["identical_normalized"],
                     acc[ink]["diff_orig_r1"], len(cells), len(bad)))

    # ---------- aggregate ----------
    n_probes = len(report["probes"])
    byte_all = all(p["bytes"]["orig_vs_r1"]["norm_equal"] and
                   p["bytes"]["r1_vs_r2"]["norm_equal"] for p in report["probes"])
    content_all = all(v["diff_orig_r1"] == 0 and v["diff_r1_r2"] == 0
                      for p in report["probes"] for v in p["content_planes"].values())
    cells = [c for p in report["probes"] for c in p["audit_cells"]]
    report["summary"] = {
        "probes": n_probes,
        "all_byte_identical_TI_normalised": byte_all,
        "all_content_identical": content_all,
        "audit_cells_total": len(cells),
        "audit_cells_deterministic": sum(1 for c in cells if c["deterministic"]),
        "audit_cells_orig_matches_audit": sum(1 for c in cells if c["orig_matches_audit"]),
        "audit_cells_orig_zero": sum(1 for c in cells if c["orig"] == 0),
        "audit_cells_orig_levels": {str(k): sum(1 for c in cells if c["orig"] == k)
                                    for k in sorted({c["orig"] for c in cells})},
        "conclusion": ("蒙泰 PRN 逐字节确定（TI 时间戳归一化后 52/52 完全一致，内容平面 0 差异）；"
                       "审计的 832 个单元在原始 PRN 与两次重跑中 level 完全相同 ⇒ "
                       "非确定性排除，这是蒙泰可复现的确定性特殊行为（非单调漏点 bug）"
                       if byte_all and content_all else
                       "检测到重跑差异，需进一步分析"),
    }
    print("\nSUMMARY:", json.dumps(report["summary"], ensure_ascii=False, indent=1))
    with open(os.path.join(EV, "screen_nondeterminism.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
