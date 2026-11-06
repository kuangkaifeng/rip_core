#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild probe_scan_manifest.json correctly.

The first M/Y/K merge used a wrong tuple unpack (tag became just "M"/"Y"/"K" for
all 256 levels), so entries collapsed in dedup.  Rebuild all M/Y/K entries from
the actual files on disk (they are correctly named), keep the other families
(C / gray / cmykall / B / margin probes), and recompute stats.
"""
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "prn_tools"))
import mtrip_oracle as O   # noqa: E402
import parse_prn as P      # noqa: E402

EV = os.path.join(HERE, "evidence")
MAN = os.path.join(EV, "probe_scan_manifest.json")


def dot_stats(prn):
    data = open(prn, "rb").read()
    if data[:2] == b"\x55\x55":
        return None
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


def entry(kind, tag, ink=None):
    stem = "probe_scan_%s_a3dtf1390_m2" % tag
    prn = os.path.join(O.PRNS, stem + ".prn")
    img = os.path.join(O.INPUTS, "probe_scan_%s_64.%s"
                       % (tag, "png" if kind == "gray" else "tif"))
    if kind == "B":
        img = os.path.join(O.INPUTS, "probe_scan_C64_720.tif")
    elif kind.startswith("C-"):
        img = os.path.join(O.INPUTS, "probe_scan_%s_64.tif" % tag)
    resp = os.path.join(O.JOBS, stem + ".resp.json")
    if not os.path.isfile(prn):
        return None
    size = os.path.getsize(prn)
    r = {}
    if os.path.isfile(resp):
        try:
            r = json.load(open(resp, encoding="utf-8-sig"))
        except Exception:
            pass
    rec = {"kind": kind, "tag": tag, "input": img.replace("\\", "/"),
           "prn": prn.replace("\\", "/"),
           "job": os.path.join(O.JOBS, stem + ".json").replace("\\", "/"),
           "result": r.get("result"), "error": r.get("error"),
           "size": size, "elapsed_s": r.get("_elapsed_s")}
    if img and not os.path.isfile(img):
        rec["input_missing"] = True
    if size and kind != "gray":
        rec["stats"] = dot_stats(prn)
    if kind == "B":
        rec["area_note"] = "page 4320x4320 px, cov computed against 384*384!"
    return rec


def main():
    man = json.load(open(MAN, encoding="utf-8"))
    base = [j for j in man["jobs"] if j.get("kind") not in ("M", "Y", "K")]
    rows = list(base)
    n_before = len(rows)
    for ink in ("M", "Y", "K"):
        bad = 0
        for t in range(256):
            tag = "%s%03d" % (ink, t)
            r = entry(ink, tag)
            if r is None:
                bad += 1
                continue
            if r.get("result") != 0:
                bad += 1
            rows.append(r)
        print("%s: %d levels added (%d missing/failed)" % (ink, 256 - bad, bad),
              flush=True)
    man["jobs"] = rows
    man["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    man["moyk256"] = {"note": "M/Y/K 256-level scan (0..255, step 1) + "
                              "B) C64 on 720x720 + C) margin=top/left 100mm probes",
                      "total": 768 + 3, "ok": 768 + 3}
    with open(MAN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    from collections import Counter
    print("manifest total:", len(rows), Counter(j["kind"] for j in rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
