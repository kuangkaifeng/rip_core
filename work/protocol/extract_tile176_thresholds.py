#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract T1/T2/T3 threshold fields for the 176x176 C/Y scans (1024 tile).

Requires numpy (installed in the Espressif python env 2026-11-06).
Outputs:
  work/protocol/evidence/probe_scan_thresholds_C176.bin
  work/protocol/evidence/probe_scan_thresholds_Y176.bin
  work/protocol/evidence/probe_scan_thresholds_176_summary.json
Layout: T1[N] T2[N] T3[N], each uint16 little-endian, N = decoded raster positions
per channel for a 176x176 input at A3-DTF-1390.prs modeId=2; raster order is the
same as the 64x64 scans (block-major -> record-major -> row-major, 4 px/byte
LSB-first; n*4 px per line, 90 lines/record).  T1=0 means the raster position is
a microweave blank-padding line (never inked); real page pixels are T1>0 and the
2-bit level is modelled as level=(3*t+D)>>8 with D in [256-3*T1, 258-3*T1].
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "prn_tools"))
import mtrip_oracle as O   # noqa: E402
import parse_prn as P      # noqa: E402

EV = os.path.join(HERE, "evidence")
MAN = os.path.join(EV, "probe_scan_manifest.json")


def levels_from_prn(prn):
    """dict code -> np.uint8 array of 2-bit levels in raster order."""
    data = open(prn, "rb").read()
    job = P.parse_job(data, decode=True)
    out = {}
    for b in job.blocks:
        for r in b.records:
            if r.raw is None:
                continue
            raw = np.frombuffer(r.raw, dtype=np.uint8)
            lv = np.empty(raw.size * 4, dtype=np.uint8)
            lv[0::4] = raw & 3
            lv[1::4] = (raw >> 2) & 3
            lv[2::4] = (raw >> 4) & 3
            lv[3::4] = (raw >> 6) & 3
            out.setdefault(r.color, []).append(lv)
    return {c: np.concatenate(v) for c, v in out.items()}


def extract(kind, ink):
    jobs = [j for j in json.load(open(MAN, encoding="utf-8"))["jobs"]
            if j.get("kind") == kind and j.get("result") == 0 and j.get("size")]
    jobs.sort(key=lambda j: int(j["tag"][1:]))
    if len(jobs) != 256:
        raise SystemExit("need 256 levels for %s, got %d" % (kind, len(jobs)))
    lv = levels_from_prn(jobs[-1]["prn"])
    code = max(lv, key=lambda c: int((lv[c] > 0).sum()))
    arr = lv[code]
    N = int(arr.size)
    page = arr > 0
    n_page = int(page.sum())
    print("%s: code 0x%02X, N=%d, page pixels(t=255)=%d" % (kind, code, N, n_page),
          flush=True)
    T1 = np.zeros(N, dtype=np.uint16)
    T2 = np.zeros(N, dtype=np.uint16)
    T3 = np.zeros(N, dtype=np.uint16)
    m1 = np.ones(N, dtype=bool)
    m2 = np.ones(N, dtype=bool)
    m3 = np.ones(N, dtype=bool)
    for j in jobs:
        t = int(j["tag"][1:])
        a = levels_from_prn(j["prn"]).get(code)
        if a is None or a.size != N:
            continue
        sel = m1 & (a > 0)
        T1[sel] = t
        m1 &= ~sel
        sel = m2 & (a >= 2)
        T2[sel] = t
        m2 &= ~sel
        sel = m3 & (a >= 3)
        T3[sel] = t
        m3 &= ~sel
        if t % 64 == 0:
            print("  %s t=%d (m1=%d m2=%d m3=%d)" % (
                kind, t, int(m1.sum()), int(m2.sum()), int(m3.sum())), flush=True)
        if not (m1.any() or m2.any() or m3.any()):
            break
    path = os.path.join(EV, "probe_scan_thresholds_%s.bin" % kind)
    with open(path, "wb") as f:
        f.write(T1.tobytes())
        f.write(T2.tobytes())
        f.write(T3.tobytes())
    cp = page & (T1 > 0)
    d12 = (T2[cp].astype(int) - T1[cp].astype(int))
    d23 = (T3[cp].astype(int) - T2[cp].astype(int))
    summ = {
        "kind": kind, "ink": ink, "n_raster": N,
        "n_page_pixels": int(cp.sum()),
        "code": "0x%02X" % code,
        "T1_hist_page": {str(k): int(v) for k, v in
                         zip(*np.unique(T1[cp], return_counts=True))},
        "T1_min": int(T1[cp].min()), "T1_max": int(T1[cp].max()),
        "d12_hist": {str(k): int(v) for k, v in
                     zip(*np.unique(d12, return_counts=True))},
        "d23_hist": {str(k): int(v) for k, v in
                     zip(*np.unique(d23, return_counts=True))},
        "D_range_from_T1": [int(256 - 3 * int(T1[cp].max())),
                            int(258 - 3 * int(T1[cp].min()))],
        "file": os.path.basename(path),
        "layout": "T1[N] T2[N] T3[N] uint16 LE; raster order same as 64x64 scans "
                  "(block-major->record-major->row-major, 4px/byte LSB-first, "
                  "n*4 px/line, 90 lines/record); T1=0 => blank padding line",
    }
    print("%s saved %s (%.2f MB), page=%d, T1 %d..%d, d12=%s, d23=%s"
          % (kind, os.path.basename(path), os.path.getsize(path) / 1048576,
             summ["n_page_pixels"], summ["T1_min"], summ["T1_max"],
             dict(list(summ["d12_hist"].items())[:4]),
             dict(list(summ["d23_hist"].items())[:4])), flush=True)
    return summ


def main():
    out = {"generated": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
           "note": "176x176 C/Y scans; content 1056x1056 output px > 1024 tile",
           "channels": {}}
    out["channels"]["C"] = extract("C176", "C")
    out["channels"]["Y"] = extract("Y176", "Y")
    with open(os.path.join(EV, "probe_scan_thresholds_176_summary.json"), "w",
              encoding="utf-8", newline="\n") as f:
        import json as _j
        _j.dump(out, f, ensure_ascii=False, indent=2)
    print("saved probe_scan_thresholds_176_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
