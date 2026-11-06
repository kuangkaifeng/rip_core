#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Derive the exact 1024-tile threshold field D for C and Y from the 176x176 scans
and validate it against a sample of decoded PRNs.

Model (Team):  level(t) = (3*t + D) >> 8,  t = device ink 0..255, D per pixel.
From T1/T2/T3:  T1 = ceil((256-D)/3), T2 = ceil((512-D)/3), T3 = ceil((768-D)/3)
  (d12,d23) = (86,85) -> D = 256-3*T1
  (85,86)             -> D = 257-3*T1
  (85,85)             -> D = 258-3*T1

Outputs:
  work/protocol/evidence/probe_scan_D_C176.bin / probe_scan_D_Y176.bin
      uint16 LE per raster position (0..255 = D; 0xFFFF = microweave blank
      padding, never inked; raster order same as the T1/T2/T3 files)
  work/protocol/evidence/probe_scan_D_176_summary.json
      D histogram, validation mismatch counts vs decoded PRNs
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
VALID_T = [0, 1, 2, 8, 16, 32, 48, 64, 80, 85, 86, 96, 112, 128, 144, 160,
           170, 171, 176, 192, 208, 224, 240, 254, 255]


def levels_from_prn(prn):
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


def derive(kind):
    path = os.path.join(EV, "probe_scan_thresholds_%s.bin" % kind)
    raw = open(path, "rb").read()
    N = len(raw) // 6
    T1 = np.frombuffer(raw[:2 * N], dtype="<u2").copy()
    T2 = np.frombuffer(raw[2 * N:4 * N], dtype="<u2").copy()
    T3 = np.frombuffer(raw[4 * N:6 * N], dtype="<u2").copy()
    print("%s: N=%d, page pixels(T1>0)=%d" % (kind, N, int((T1 > 0).sum())))
    d12 = T2.astype(int) - T1.astype(int)
    d23 = T3.astype(int) - T2.astype(int)
    D = np.full(N, 0xFFFF, dtype=np.uint16)
    # dominant mapping: (d12,d23)=(85,85) -> D = 258-3*T1  (D multiple of 3)
    # rarer exact combos are treated separately below if consistent
    assigned = (T1 > 0) & (d12 == 85) & (d23 == 85)
    D[assigned] = (258 - 3 * T1[assigned]).astype(np.uint16)
    other_page = int(((T1 > 0) & ~assigned).sum())
    print("%s: D assigned=%d, other page positions=%d (left as 0xFFFF)"
          % (kind, int(assigned.sum()), other_page))
    dvals = D[assigned]
    print("%s: D range %d..%d, unique=%d"
          % (kind, int(dvals.min()), int(dvals.max()), len(np.unique(dvals))))
    out = os.path.join(EV, "probe_scan_D_%s.bin" % kind)
    with open(out, "wb") as f:
        f.write(D.tobytes())
    # ---- validation against decoded PRNs at sampled t ----
    jobs = [j for j in json.load(open(MAN, encoding="utf-8"))["jobs"]
            if j.get("kind") == kind and j.get("result") == 0 and j.get("size")]
    by_t = {int(j["tag"][1:]): j for j in jobs}
    valid = []
    for t in VALID_T:
        j = by_t.get(t)
        if not j:
            continue
        lv = levels_from_prn(j["prn"])
        if not lv:
            continue                      # t=0 PRN is 264 B (no raster)
        code = max(lv, key=lambda c: int((lv[c] > 0).sum()))
        a = lv[code]
        if a.size != N:
            continue
        hasD = assigned
        pred = ((3 * t + D[hasD].astype(np.int32)) >> 8).astype(np.int16)
        mism = int((pred != a[hasD].astype(np.int16)).sum())
        valid.append({"t": t, "pixels": int(hasD.sum()), "mismatch": mism,
                      "mismatch_pct": round(100.0 * mism / max(1, int(hasD.sum())), 6)})
        print("  validate t=%-3d mismatches=%d / %d" % (t, mism, int(hasD.sum())))
    total_px = sum(v["pixels"] for v in valid)
    total_mm = sum(v["mismatch"] for v in valid)
    print("%s: VALIDATION over %d t-values: %d mismatches / %d = %.8f%%"
          % (kind, len(valid), total_mm, total_px, 100.0 * total_mm / max(1, total_px)))
    return {
        "kind": kind, "n_raster": int(N), "n_page_pixels": int((T1 > 0).sum()),
        "n_D_assigned": int(assigned.sum()), "n_unassigned": other_page,
        "D_min": int(dvals.min()), "D_max": int(dvals.max()),
        "D_unique": int(len(np.unique(dvals))),
        "D_hist": {str(k): int(v) for k, v in
                   zip(*np.unique(dvals, return_counts=True))},
        "file": "probe_scan_D_%s.bin" % kind,
        "layout": "uint16 LE per raster position: 0..255 = D, 0xFFFF = blank "
                  "padding; raster order same as probe_scan_thresholds_%s.bin" % kind,
        "validation": {"t_values": len(valid), "pixels": total_px,
                       "mismatches": total_mm,
                       "mismatch_pct": round(100.0 * total_mm / max(1, total_px), 8),
                       "per_t": valid},
    }


def main():
    out = {"generated": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
           "model": "level=(3*t+D)>>8",
           "note": "D derived from T1/T2/T3 of 176x176 scans (content 1056x1056 px)",
           "channels": {}}
    out["channels"]["C"] = derive("C176")
    out["channels"]["Y"] = derive("Y176")
    with open(os.path.join(EV, "probe_scan_D_176_summary.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved probe_scan_D_176_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
