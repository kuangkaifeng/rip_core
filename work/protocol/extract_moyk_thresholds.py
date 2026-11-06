#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract high-precision threshold fields T1/T2/T3 for M/Y/K from the 256-level
scan, verify the Team model `level=(3*v+D)>>8`, and compare channels.

Optimisation: positions that are 0 in the t=255 PRN are microweave blank
padding lines (never inked); skip them so the per-position threshold scan only
runs over the 384x384 real page pixels.

Output:
  work/protocol/evidence/probe_scan_thresholds_<INK>.bin   (T1,T2,T3 uint16 LE)
  work/protocol/evidence/probe_scan_thresholds_MYK_summary.json
"""
import json
import os
import struct
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "prn_tools"))
import mtrip_oracle as O   # noqa: E402
import parse_prn as P      # noqa: E402

EV = os.path.join(HERE, "evidence")
MAN = os.path.join(EV, "probe_scan_manifest.json")
N = 96 * 4 * 90 * 13          # 449,280 raster positions


def level_array(prn):
    """Flattened 2-bit level array of the channel record order in the PRN."""
    data = open(prn, "rb").read()
    if data[:2] == b"\x55\x55":
        return None
    job = P.parse_job(data, decode=True)
    out = {}
    for b in job.blocks:
        for r in b.records:
            if r.raw is None:
                continue
            lv = bytearray(r.n * 4 * r.m)
            k = 0
            for byte in r.raw:
                lv[k] = byte & 3
                lv[k + 1] = (byte >> 2) & 3
                lv[k + 2] = (byte >> 4) & 3
                lv[k + 3] = (byte >> 6) & 3
                k += 4
            out.setdefault(r.color, bytearray()).extend(lv)
    return out


def extract(ink):
    jobs = [j for j in json.load(open(MAN, encoding="utf-8"))["jobs"]
            if j.get("kind") == ink and j.get("result") == 0 and j.get("size")]
    jobs.sort(key=lambda j: int(j["tag"][1:]))
    if len(jobs) != 256:
        raise SystemExit("need 256 levels for %s, got %d" % (ink, len(jobs)))
    # blank mask from t=255; pick the code that actually carries this channel's ink
    lv255 = level_array(jobs[-1]["prn"])
    if not lv255:
        raise SystemExit("cannot decode t=255 for %s" % ink)

    def ink_count(arr):
        return sum(1 for v in arr if v)

    code = max(lv255, key=lambda c: ink_count(lv255[c]))
    arr255 = lv255[code]
    print("%s: channel colour code 0x%02X, t=255 ink px=%d"
          % (ink, code, ink_count(arr255)), flush=True)
    inked = bytearray(N)
    for i, v in enumerate(arr255):
        if v:
            inked[i] = 1
    pos = [i for i in range(N) if inked[i]]
    print("%s: %d inked page positions (%.1f%% of raster)"
          % (ink, len(pos), 100.0 * len(pos) / N), flush=True)
    T1 = {i: 0 for i in pos}
    T2 = {i: 0 for i in pos}
    T3 = {i: 0 for i in pos}
    for j in jobs:
        t = int(j["tag"][1:])
        if not (j.get("size") or 0):
            continue
        lv = level_array(j["prn"])
        if not lv:
            continue
        a = lv.get(code) or lv[max(lv, key=lambda c: ink_count(lv[c]))]
        if len(a) != N:
            continue
        for i in pos:
            v = a[i]
            if v:
                if not T1[i]:
                    T1[i] = t
                if v >= 2 and not T2[i]:
                    T2[i] = t
                if v >= 3 and not T3[i]:
                    T3[i] = t
        if t % 64 == 0:
            print("  %s t=%d" % (ink, t), flush=True)
    T1a = [T1.get(i, 0) for i in range(N)]
    T2a = [T2.get(i, 0) for i in range(N)]
    T3a = [T3.get(i, 0) for i in range(N)]
    bin_path = os.path.join(EV, "probe_scan_thresholds_%s.bin" % ink)
    with open(bin_path, "wb") as f:
        for arr in (T1a, T2a, T3a):
            f.write(struct.pack("<%dH" % N, *arr))
    d12 = Counter(T2a[i] - T1a[i] for i in pos if T2a[i])
    d23 = Counter(T3a[i] - T2a[i] for i in pos if T3a[i] and T2a[i])
    # D estimate from T1: T1 = ceil((256-D)/3) -> D in [256-3*T1, 258-3*T1]
    Dmin = Counter(256 - 3 * T1a[i] for i in pos)
    ok = sum(1 for i in pos if T1a[i] and T2a[i] and T3a[i])
    summ = {
        "ink": ink, "n_raster": N, "n_page_pixels": len(pos),
        "T1_hist": {str(k): v for k, v in sorted(Counter(T1a[i] for i in pos).items())},
        "d12_hist": {str(k): v for k, v in sorted(d12.items())},
        "d23_hist": {str(k): v for k, v in sorted(d23.items())},
        "T1_min": min(T1a[i] for i in pos), "T1_max": max(T1a[i] for i in pos),
        "D_est_from_T1": {
            "formula": "T1 = ceil((256-D)/3) => D in [256-3*T1, 258-3*T1]",
            "D_min_hist": {str(k): v for k, v in sorted(Dmin.items())},
        },
        "pixels_with_all_T": ok,
        "file": "probe_scan_thresholds_%s.bin" % ink,
        "layout": "T1[%d] T2[%d] T3[%d] uint16 LE (same raster order as C scan)"
                  % (N, N, N),
    }
    print("%s: T1 %d..%d, d12=%s d23=%s Dmin_range=%s"
          % (ink, summ["T1_min"], summ["T1_max"],
             dict(d12.most_common(3)), dict(d23.most_common(3)),
             (min(Dmin), max(Dmin))), flush=True)
    return summ


def main():
    summary = {"generated": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
               "model": "level=(3*v+D)>>8, D per-channel random field",
               "channels": {}}
    for ink in ("M", "Y", "K"):
        summary["channels"][ink] = extract(ink)

    # cross-channel check: do channels share the threshold field?
    # reuse the C scan arrays already extracted (probe_scan_thresholds.bin)
    cross = {}
    cbin = os.path.join(EV, "probe_scan_thresholds.bin")
    if os.path.isfile(cbin):
        data = open(cbin, "rb").read()
        n = len(data) // 6
        T1c = list(struct.unpack("<%dH" % n, data[:2 * n]))
        for ink in ("M", "Y", "K"):
            b = open(os.path.join(EV, "probe_scan_thresholds_%s.bin" % ink), "rb").read()
            T1x = list(struct.unpack("<%dH" % n, b[:2 * n]))
            both = [(a, c) for a, c in zip(T1c, T1x) if a and c]
            same = sum(1 for a, c in both if a == c)
            cross[ink + "_vs_C"] = {"pixels": len(both), "same_T1": same,
                                    "different": len(both) - same}
    summary["cross_channel"] = cross
    with open(os.path.join(EV, "probe_scan_thresholds_MYK_summary.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("cross:", cross)
    print("saved probe_scan_thresholds_MYK_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
