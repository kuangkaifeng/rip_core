#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FINAL high-precision M/Y/K threshold-field probes (Lead request A, + B/C).

A) M/Y/K each 256 levels (t=0..255, step 1), 64x64 CMYK TIFF, A3 mode2:
     reference/inputs/probe_scan_<INK>###_64.tif
     reference/prn_samples/probe_scan_<INK>###_a3dtf1390_m2.prn
B) C=64 on 720x720 CMYK TIFF -> probe_scan_C64_720.* (tile-period check)
C) C=64 64x64 with margin top=100mm / left=100mm (D-field index coordinate test)

Merges every new job into work/protocol/evidence/probe_scan_manifest.json
(existing C/gray/cmykall/old-MYK entries are kept; M/Y/K tags replaced by the
full 0..255 set).  Sequential POST only.
"""
import json
import os
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "prn_tools"))
import mtrip_oracle as O   # noqa: E402

EV = os.path.join(HERE, "evidence")
MAN = os.path.join(EV, "probe_scan_manifest.json")
DPI = (120, 120)
PRS = "./A3-DTF-1390.prs"


def mk_cmyk(name, c=0, m=0, y=0, k=0, size=64):
    path = os.path.join(O.INPUTS, name)
    Image.new("CMYK", (size, size), (c, m, y, k)).save(path, "TIFF", dpi=DPI)
    return path


def dot_stats(prn):
    data = open(prn, "rb").read()
    if data[:2] == b"\x55\x55":
        return None
    import parse_prn as P
    job = P.parse_job(data, decode=True)
    per = {}
    for b in job.blocks:
        for r in b.records:
            d = per.setdefault(r.color, {"ink": 0, "hist": {1: 0, 2: 0, 3: 0}})
            if r.raw:
                for byte in r.raw:
                    for sh in (0, 2, 4, 6):
                        v = (byte >> sh) & 3
                        if v:
                            d["ink"] += 1
                            d["hist"][v] += 1
    area = 384 * 384
    out = []
    for c, d in sorted(per.items()):
        if not d["ink"]:
            continue
        avg = sum(k * v for k, v in d["hist"].items()) / d["ink"]
        out.append({"code": "0x%02X" % c, "ink_px": d["ink"],
                    "cov": round(d["ink"] / area, 6),
                    "avg_dot_of_inked": round(avg, 6),
                    "avg_dot_of_page": round(d["ink"] * avg / area, 6),
                    "hist": {"%d" % k: v for k, v in d["hist"].items()}})
    return out


def health():
    try:
        return O.get("/mtrip/v1/status").get("result") == 0
    except Exception:
        return False


def run_one(kind, tag, image, extra=None, prn_tag=None, rows_total=None, idx=0):
    stem = "probe_scan_%s_a3dtf1390_m2" % (prn_tag or tag)
    img = image.replace("\\", "/")
    out = os.path.join(O.PRNS, stem + ".prn").replace("\\", "/")
    job = O.build_job(img, PRS, 2, out, extra=extra)
    t0 = time.time()
    try:
        r = O.run_job(job, stem)
        rec = {"kind": kind, "tag": tag, "input": img, "prn": out,
               "job": os.path.join(O.JOBS, stem + ".json"),
               "result": r["response"].get("result"),
               "error": r["response"].get("error"),
               "size": r["prn_size"],
               "elapsed_s": r["response"].get("_elapsed_s", round(time.time() - t0, 3)),
               "extra": extra}
        if r["prn_size"]:
            rec["stats"] = dot_stats(out)
            rec["sha256_norm"] = O.sha256_file(out, normalize=True)
    except Exception as e:
        rec = {"kind": kind, "tag": tag, "input": img, "prn": out,
               "result": "CONN_ERR", "error": repr(e), "size": 0}
    if rows_total and (idx % 25 == 0 or idx == rows_total):
        print("  %d/%d %s" % (idx, rows_total, tag), flush=True)
    return rec


def main():
    plan = []
    print("generating inputs ...", flush=True)
    # A) M/Y/K 256 levels each
    for ink in ("M", "Y", "K"):
        kw_name = {"M": "m", "Y": "y", "K": "k"}[ink]
        for t in range(256):
            tag = "%s%03d" % (ink, t)
            path = mk_cmyk("probe_scan_%s_64.tif" % tag, **{kw_name: t})
            plan.append(("A-" + ink, ink, tag, path, None))
    # B) C=64, 720x720
    plan.append(("B", "C64_720", "C64_720",
                 mk_cmyk("probe_scan_C64_720.tif", c=64, size=720), None))
    # C) C=64 with margins (top=100mm / left=100mm)
    plan.append(("C-top100", "C64_marginT100", "C64_marginT100",
                 mk_cmyk("probe_scan_C64_marginT100_64.tif", c=64),
                 {"margin": [0, 100, 0, 0]}))
    plan.append(("C-left100", "C64_marginL100", "C64_marginL100",
                 mk_cmyk("probe_scan_C64_marginL100_64.tif", c=64),
                 {"margin": [100, 0, 0, 0]}))
    total = len(plan)
    print("total jobs:", total, flush=True)

    new_rows = []
    for i, (kind, tag, prn_tag, img, extra) in enumerate(plan, 1):
        if i % 50 == 0 and not health():
            print("!! oracle not healthy at job %d, stop" % i, flush=True)
            break
        new_rows.append(run_one(kind, tag, img, extra=extra, prn_tag=prn_tag,
                                rows_total=total, idx=i))

    # merge into manifest (replace same kind+tag, keep everything else)
    man = json.load(open(MAN, encoding="utf-8"))
    repl = {(r["kind"], r["tag"]): r for r in new_rows}
    kept = [j for j in man["jobs"]
            if (j.get("kind"), j.get("tag")) not in repl]
    man["jobs"] = kept + new_rows
    man["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    man["moyk256"] = {"note": "M/Y/K 256-level scan + C64_720 (B) + margin probes (C)",
                      "total": len(new_rows),
                      "ok": sum(1 for r in new_rows if r.get("result") == 0)}
    with open(MAN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    total_size = sum(r.get("size") or 0 for r in new_rows)
    ok = sum(1 for r in new_rows if r.get("result") == 0)
    print("\nmerged manifest: %d jobs total; this run: %d ok/%d, PRN %.2f MB"
          % (len(man["jobs"]), ok, len(new_rows), total_size / 1048576.0))
    return 0 if ok == len(new_rows) else 1


if __name__ == "__main__":
    sys.exit(main())
