#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the reference PRN corpus through the mtripNet HTTP oracle.

Naming (documented in docs/maintop_api.md):
    reference/prn_samples/<machine>_<case>_m<modeId>[_<variant>].prn
    reference/jobs/<same stem>.json           job JSON actually POSTed
    reference/jobs/<same stem>.resp.json      server response (+_elapsed_s)
    reference/jobs/manifest.csv               one row per generated PRN

machine: a3dtf1390 (A3-DTF-1390.prs, modified Epson 1390 -> ESC/P2)
         h13xp600   (H13 XP600.prs, board machine -> HSSF 0x5555)
case:    input image stem from reference/inputs/
variant: whiteink template variant when != base (golden / w1w2)

Sequential only (single POST at a time).  Safe to re-run: existing successful
jobs are skipped unless --force is given.

Usage:
    python tools/oracle/make_corpus.py [--force] [--only base|white|big] [--limit N]
"""
import argparse
import csv
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import mtrip_oracle as O   # noqa: E402

MACHINES = {
    "a3dtf1390": {"prs": "./A3-DTF-1390.prs", "modes": [0, 1, 2, 3]},
    "h13xp600": {"prs": O.PRS["h13xp600"], "modes": [0, 1, 2, 3]},
}

BASE_CASES = [
    "flat_black_100", "flat_white_100", "flat_c_100", "flat_m_100",
    "flat_y_100", "flat_k_100", "flat_r_100", "flat_g_100", "flat_b_100",
    "cmyk_quad_100", "rgb_quad_100", "checker_1px_100", "checker_8px_100",
    "grad_h_100", "grad_v_100", "lines_1px_100",
    "alpha_checker_100", "alpha_grad_100",
]

# extra white-ink variants on modes that own W channels
WHITE_CASES = {
    "a3dtf1390": [(1, "golden"), (3, "golden"), (3, "w1w2"), (2, "golden")],
    "h13xp600": [(0, "golden"), (1, "golden"), (0, "w1w2")],
}
WHITE_IMAGES = ["flat_black_100", "cmyk_quad_100", "alpha_checker_100"]

BIG_CASES = [
    ("a3dtf1390", 2, "cmyk_quad_720"),
    ("a3dtf1390", 2, "checker_8px_720"),
    ("h13xp600", 0, "cmyk_quad_720"),
]

MANIFEST = os.path.join(O.JOBS, "manifest.csv")
FIELDS = ["stem", "machine", "prs", "modeId", "case", "image", "variant",
          "result", "elapsed_s", "prn", "size", "sha256", "sha256_norm"]


def stem_for(machine, case, mode, variant="base"):
    s = f"{machine}_{case}_m{mode}"
    if variant and variant != "base":
        s += "_" + variant
    return s


def ok_already(stem, force):
    if force:
        return False
    resp = os.path.join(O.JOBS, stem + ".resp.json")
    prn = os.path.join(O.PRNS, stem + ".prn")
    if not (os.path.isfile(resp) and os.path.isfile(prn) and os.path.getsize(prn) > 0):
        return False
    try:
        r = json.load(open(resp, encoding="utf-8-sig"))
    except Exception:
        return False
    return r.get("result") == 0


def do_job(machine, case, mode, variant="base", force=False, rows=None):
    stem = stem_for(machine, case, mode, variant)
    img = os.path.join(WS, "reference", "inputs", case + ".png").replace("\\", "/")
    out = os.path.join(O.PRNS, stem + ".prn").replace("\\", "/")
    if ok_already(stem, force):
        print(f"skip  {stem}")
        if rows is not None:
            rows.append(existing_row(stem, machine, case, mode, variant))
        return None
    spec = MACHINES[machine]
    job = O.build_job(img, spec["prs"], mode, out,
                      white="none" if variant == "base" else variant)
    t0 = time.time()
    r = O.run_job(job, stem)
    dt = round(time.time() - t0, 3)
    resp = r["response"]
    rec = {"stem": stem, "machine": machine, "prs": spec["prs"], "modeId": mode,
           "case": case, "image": img, "variant": variant,
           "result": resp.get("result"), "elapsed_s": resp.get("_elapsed_s", dt),
           "prn": out, "size": r["prn_size"],
           "sha256": O.sha256_file(out) if r["prn_size"] else "",
           "sha256_norm": O.sha256_file(out, normalize=True) if r["prn_size"] else ""}
    if rows is not None:
        rows.append(rec)
    print(f"{'OK ' if rec['result'] == 0 else 'ERR'}   {stem:52s} "
          f"mode={mode} variant={variant:7s} result={rec['result']} "
          f"size={rec['size']:>10d} t={rec['elapsed_s']}s")
    return rec


def existing_row(stem, machine, case, mode, variant):
    resp_path = os.path.join(O.JOBS, stem + ".resp.json")
    prn = os.path.join(O.PRNS, stem + ".prn")
    try:
        r = json.load(open(resp_path, encoding="utf-8-sig"))
    except Exception:
        r = {}
    return {"stem": stem, "machine": machine, "prs": MACHINES[machine]["prs"],
            "modeId": mode, "case": case,
            "image": os.path.join(WS, "reference", "inputs", case + ".png").replace("\\", "/"),
            "variant": variant, "result": r.get("result"),
            "elapsed_s": r.get("_elapsed_s", ""), "prn": prn,
            "size": os.path.getsize(prn) if os.path.isfile(prn) else 0,
            "sha256": O.sha256_file(prn) if os.path.isfile(prn) else "",
            "sha256_norm": O.sha256_file(prn, normalize=True) if os.path.isfile(prn) else ""}


def write_manifest(rows):
    seen, uniq = set(), []
    for r in rows:
        if r["stem"] not in seen:
            seen.add(r["stem"])
            uniq.append(r)
    uniq.sort(key=lambda r: (r["machine"], r["case"], r["modeId"], r["variant"]))
    os.makedirs(O.JOBS, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in uniq:
            w.writerow(r)
    print(f"manifest: {MANIFEST} ({len(uniq)} jobs)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="all", choices=["all", "base", "white", "big"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    rows = []
    t0 = time.time()
    n = 0
    try:
        if args.only in ("all", "base"):
            print("=== base corpus: machine x mode x 18 cases ===")
            for machine, spec in MACHINES.items():
                for mode in spec["modes"]:
                    for case in BASE_CASES:
                        rec = do_job(machine, case, mode, "base", args.force, rows)
                        n += 1
                        if args.limit and n >= args.limit:
                            raise SystemExit(0)
        if args.only in ("all", "white"):
            print("=== white-ink corpus ===")
            for machine, combos in WHITE_CASES.items():
                for mode, variant in combos:
                    for case in WHITE_IMAGES:
                        do_job(machine, case, mode, variant, args.force, rows)
                        n += 1
                        if args.limit and n >= args.limit:
                            raise SystemExit(0)
        if args.only in ("all", "big"):
            print("=== big (720x720) corpus ===")
            for machine, mode, case in BIG_CASES:
                do_job(machine, case, mode, "base", args.force, rows)
                n += 1
                if args.limit and n >= args.limit:
                    raise SystemExit(0)
    finally:
        if rows:
            write_manifest(rows)
        print(f"elapsed {time.time()-t0:.1f}s, jobs this run: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
