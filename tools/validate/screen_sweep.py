#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screen_sweep.py —— 全 256 级 × C/M/Y/K 加网阈值场复核（C++ 解码器独立验证）

输出 JSONL：每行 = {ink, tone, content, mismatches:[{x,y,pred,got}...], acc}
用法: python tools/validate/screen_sweep.py [--out tools/validate/out/screen_sweep.jsonl]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

WS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXE = os.path.join(WS, "build", "mtr_prncheck.exe")
PRN = os.path.join(WS, "reference", "prn_samples")
SCREEN = os.path.join(WS, "reference", "screen", "final")
TILE = 1024
INK_RECORD = {"K": (0, 0x04), "C": (1, 0x00), "M": (2, 0x12), "Y": (3, 0x11)}


def load_thr(ink):
    return open(os.path.join(SCREEN, f"thr_{ink}.bin"), "rb").read()


def decode_content(prn_path, tmpdir):
    subprocess.run([EXE, "content", prn_path, "--mode", "2", "--out", tmpdir],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    return glob.glob(os.path.join(tmpdir, "content_*.bin"))


def check(sink, tone, thr, out):
    ink = sink
    content = 176
    prn = os.path.join(PRN, f"probe_scan_{ink}{tone:03d}_{content}_a3dtf1390_m2.prn")
    if not os.path.exists(prn):
        out.write(json.dumps(dict(ink=ink, tone=tone, skip="probe missing")) + "\n")
        return None
    tmp = tempfile.mkdtemp(prefix="mtrsweep_")
    try:
        files = decode_content(prn, tmp)
        rec, code = INK_RECORD[ink]
        target = [f for f in files if os.path.basename(f).startswith(f"content_{rec}_{code:02x}.w")]
        if not target:
            out.write(json.dumps(dict(ink=ink, tone=tone, skip="plane missing")) + "\n")
            return None
        plane = open(target[0], "rb").read()
        base = os.path.basename(target[0])
        wh = base.split(".w")[1].split(".bin")[0]
        W, H = (int(x) for x in wh.split("h"))
        N = min(W, H, TILE)
        bad = []
        for y in range(N):
            row = y * W
            to = y * TILE * 3
            for x in range(N):
                o = to + x * 3
                T1, T2, T3 = thr[o], thr[o + 1], thr[o + 2]
                pred = ((1 if T1 and tone >= T1 else 0)
                        + (1 if T2 and tone >= T2 else 0)
                        + (1 if T3 and tone >= T3 else 0))
                got = plane[row + x]
                if pred != got:
                    bad.append([x, y, pred, got])
        acc = 100.0 * (N * N - len(bad)) / (N * N)
        out.write(json.dumps(dict(ink=ink, tone=tone, content=f"{W}x{H}",
                                  n=N, mismatches=bad, acc=acc)) + "\n")
        out.flush()
        return bad
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(WS, "tools", "validate", "out",
                                                  "screen_sweep.jsonl"))
    ap.add_argument("--inks", default="C,M,Y,K")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    thr = {ink: load_thr(ink) for ink in INK_RECORD}
    total_bad = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for ink in args.inks.split(","):
            for tone in range(256):
                bad = check(ink, tone, thr[ink], out)
                if bad:
                    total_bad += 1
                    print(f"  {ink}{tone:03d}: {len(bad)} mismatches "
                          f"(first {bad[:3]})", flush=True)
    print(f"\nwrote {args.out}; probes with mismatches = {total_bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
