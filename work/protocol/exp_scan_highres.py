#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""High-precision screening threshold-field probe (final T6 task).

For each probe: one 64x64 input image with a known device-ink value, run through
the mtripNet oracle on A3-DTF-1390.prs modeId=2 (720x720dpi CMYK, no ICC),
and decode the PRN 2-bit raster to measure the realised dot statistics.

Probe families
  C        : C=t (t=0..255, all 256 values)        -> probe_scan_C###_64.tif
  M/Y/K    : ink=t (t=0,8,...,248, 32 values each) -> probe_scan_<INK>###_64.tif
  gray     : RGB neutral R=G=B=t (32 values)       -> probe_scan_gray###_64.png
  cmykall  : C=M=Y=K=t (16 values, step 17)        -> probe_scan_cmykall###_64.tif

Output:
  reference/inputs/probe_scan_*.{tif,png}
  reference/prn_samples/probe_scan_*_a3dtf1390_m2.prn
  reference/jobs/<stem>.json / .resp.json
  work/protocol/evidence/probe_scan_manifest.json

Sequential POST only; checks the oracle every 50 jobs and aborts cleanly if it
goes away.
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
DPI = (120, 120)
PRS = "./A3-DTF-1390.prs"


def mk_cmyk(name, c=0, m=0, y=0, k=0):
    path = os.path.join(O.INPUTS, name)
    Image.new("CMYK", (64, 64), (c, m, y, k)).save(path, "TIFF", dpi=DPI)
    return path


def mk_rgb(name, v):
    path = os.path.join(O.INPUTS, name)
    Image.new("RGB", (64, 64), (v, v, v)).save(path, "PNG", dpi=DPI)
    return path


def dot_stats(prn):
    """Decode PRN, return list of {code, ink_px, area, cov, avg_dot, hist}."""
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
    area = 384 * 384          # 64 px @120 dpi, mode2 = 720x720 dpi
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


def run_one(kind, tag, image, rows, n, total):
    stem = "probe_scan_%s_a3dtf1390_m2" % tag
    img = image.replace("\\", "/")
    out = os.path.join(O.PRNS, stem + ".prn").replace("\\", "/")
    job = O.build_job(img, PRS, 2, out)
    t0 = time.time()
    try:
        r = O.run_job(job, stem)
        rec = {"kind": kind, "tag": tag, "input": img, "prn": out,
               "job": os.path.join(O.JOBS, stem + ".json"),
               "result": r["response"].get("result"),
               "error": r["response"].get("error"),
               "size": r["prn_size"],
               "elapsed_s": r["response"].get("_elapsed_s", round(time.time() - t0, 3))}
        if r["prn_size"]:
            rec["stats"] = dot_stats(out)
            rec["sha256_norm"] = O.sha256_file(out, normalize=True)
    except Exception as e:
        rec = {"kind": kind, "tag": tag, "input": img, "prn": out,
               "result": "CONN_ERR", "error": repr(e), "size": 0}
    rows.append(rec)
    done = len(rows)
    if done % 25 == 0 or done == total:
        ok = sum(1 for x in rows if x.get("result") == 0)
        print("  %d/%d done, ok=%d, last=%s" % (done, total, ok, tag), flush=True)
    return rec


def main():
    os.makedirs(EV, exist_ok=True)
    jobs_plan = []      # (kind, tag, imagepath)
    print("generating inputs ...", flush=True)
    for t in range(256):
        tag = "C%03d" % t
        jobs_plan.append(("C", tag, mk_cmyk("probe_scan_%s_64.tif" % tag, c=t)))
    for ink in ("M", "Y", "K"):
        for t in range(0, 256, 8):
            tag = "%s%03d" % (ink, t)
            kw = {"M": dict(m=t), "Y": dict(y=t), "K": dict(k=t)}[ink]
            jobs_plan.append((ink, tag, mk_cmyk("probe_scan_%s_64.tif" % tag, **kw)))
    for t in range(0, 256, 8):
        tag = "gray%03d" % t
        jobs_plan.append(("gray", tag, mk_rgb("probe_scan_%s_64.png" % tag, t)))
    for i in range(16):
        t = i * 17
        tag = "cmykall%03d" % t
        jobs_plan.append(("cmykall", tag,
                          mk_cmyk("probe_scan_%s_64.tif" % tag, c=t, m=t, y=t, k=t)))
    print("total jobs:", len(jobs_plan), flush=True)

    rows = []
    for i, (kind, tag, img) in enumerate(jobs_plan):
        if i and i % 50 == 0 and not health():
            print("!! oracle not healthy at job %d, stop" % i, flush=True)
            break
        run_one(kind, tag, img, rows, i + 1, len(jobs_plan))

    manifest = {
        "note": "A3-DTF-1390.prs modeId=2, 64x64 CMYK/RGB probes, view120, base template; "
                "stats decoded from PRN 2-bit raster (page area 384x384 px)",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "prs": PRS, "modeId": 2, "total_planned": len(jobs_plan),
        "total_done": len(rows),
        "ok": sum(1 for r in rows if r.get("result") == 0),
        "failed": [r for r in rows if r.get("result") != 0],
        "jobs": rows,
    }
    path = os.path.join(EV, "probe_scan_manifest.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    total_size = sum(r.get("size") or 0 for r in rows)
    print("\nsaved %s" % path)
    print("jobs=%d ok=%d failed=%d prn_total=%.2f MB"
          % (len(rows), manifest["ok"], len(manifest["failed"]),
             total_size / 1048576.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
