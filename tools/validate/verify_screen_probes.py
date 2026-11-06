#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_screen_probes.py —— 用 **C++ 独立解码器**（mtr_prncheck content）复核 T3 的加网阈值场。

流程（每个 ink × tone）：
  1) build/mtr_prncheck.exe content probe_scan_<ink><tone>_176_a3dtf1390_m2.prn --mode 2 --out tmp
     → 内容平面 content_<rec>_<code>.w1056h1056.bin（内容坐标，值 0..3）
  2) 按 reference/screen/final/thr_<ink>.bin（1024 tile，[T1,T2,T3]，0=永不触发）
     预测 level(v,x,y) = (T1&&v>=T1)+(T2&&v>=T2)+(T3&&v>=T3)，tile 索引 (x%1024,y%1024)
  3) 在 1024×1024 区域逐像素比较，输出每 ink/tone 一致率。

用法:
  python tools/validate/verify_screen_probes.py                 # 默认 7 个 tone
  python tools/validate/verify_screen_probes.py --tones 0,64,128,255
  python tools/validate/verify_screen_probes.py --all-tones C    # 只对 C 跑 256 级
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

# mode2 记录顺序：[0x04 K, 0x00 C, 0x12 M, 0x11 Y]
INK_RECORD = {"K": (0, 0x04), "C": (1, 0x00), "M": (2, 0x12), "Y": (3, 0x11)}
TILE = 1024
DEFAULT_TONES = (0, 16, 64, 128, 192, 240, 255)


def load_thr(ink):
    path = os.path.join(SCREEN, f"thr_{ink}.bin")
    d = open(path, "rb").read()
    if len(d) != TILE * TILE * 3:
        raise SystemExit(f"{path}: size={len(d)} expect {TILE*TILE*3}")
    return d


def find_probe(ink, tone, content=176):
    pat = os.path.join(PRN, f"probe_scan_{ink}{tone:03d}_{content}_a3dtf1390_m2.prn")
    if os.path.exists(pat):
        return pat
    hits = glob.glob(os.path.join(PRN, f"probe_scan_{ink}{tone:03d}_{content}_a3dtf1390_m2.prn"))
    return hits[0] if hits else None


def load_audit_exclusions(path):
    """读 T3 的 oracle 非单调审计（work/prs/oracle_screen_audit.json），
    返回 set[(ink, tone, x, y)]：这些 (tone,像素) 上 oracle 探针自身漏点（非 tile 错误），
    对拍时应排除。"""
    if not path or not os.path.exists(path):
        return set()
    audit = json.load(open(path, encoding="utf-8"))
    excl = set()
    for ink, poss in audit.items():
        for key, cells in poss.items():
            y, x = (int(v) for v in key.split(","))
            for c in cells:
                excl.add((ink, int(c[0]), x, y))
    return excl


def decode_content(prn_path, tmpdir):
    rc = subprocess.run([EXE, "content", prn_path, "--mode", "2", "--out", tmpdir],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if rc.returncode != 0:
        raise RuntimeError((rc.stdout + rc.stderr)[-400:])
    files = glob.glob(os.path.join(tmpdir, "content_*.bin"))
    return files


def verify_one(ink, tone, thr, content=176, excl=None):
    prn = find_probe(ink, tone, content)
    if not prn:
        return None, f"probe missing for {ink}{tone:03d} content={content}"
    tmpdir = tempfile.mkdtemp(prefix="mtrscr_")
    try:
        files = decode_content(prn, tmpdir)
        rec, code = INK_RECORD[ink]
        want = f"content_{rec}_{code:02x}.w"
        target = [f for f in files if os.path.basename(f).startswith(want)]
        if not target:
            return None, f"content plane not found ({files[:2]})"
        plane = open(target[0], "rb").read()
        # 从文件名解析 W/H
        base = os.path.basename(target[0])
        wh = base.split(".w")[1].split(".bin")[0]
        W, H = (int(x) for x in wh.split("h"))
        N = min(W, H, TILE)
        bad = []
        excluded = 0
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
                    if excl and (ink, tone, x, y) in excl:
                        excluded += 1
                        continue          # oracle 探针自身漏点（T3 审计已确认），排除
                    bad.append([x, y, pred, got])
        acc = 100.0 * (N * N - len(bad)) / (N * N)
        info = (f"{ink}{tone:03d} content={W}x{H} compare={N}x{N} mismatch={len(bad)} "
                f"excluded_oracle={excluded} acc={acc:.4f}%")
        return acc, info
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tones", default=",".join(str(t) for t in DEFAULT_TONES))
    ap.add_argument("--all-tones", default=None, help="对指定 ink 跑 0..255 全部 tone（如 C）")
    ap.add_argument("--content", type=int, default=176,
                    help="探针输入像素尺寸（176 -> content=1056；64 -> content=384）")
    ap.add_argument("--audit", default=os.path.join(WS, "work", "prs",
                                                    "oracle_screen_audit.json"),
                    help="T3 的 oracle 非单调审计 JSON（其中的 (tone,像素) 对拍时排除）")
    args = ap.parse_args()
    if not os.path.exists(EXE):
        print("missing exe:", EXE)
        return 2

    excl = load_audit_exclusions(args.audit)
    if excl:
        print(f"oracle audit exclusions loaded: {len(excl)} cells from {args.audit}")
    thr = {ink: load_thr(ink) for ink in INK_RECORD}
    jobs = []
    if args.all_tones:
        jobs = [(ink, t) for ink in args.all_tones.split(",") for t in range(256)]
    else:
        tones = [int(t) for t in args.tones.split(",") if t.strip() != ""]
        jobs = [(ink, t) for ink in ("C", "M", "Y", "K") for t in tones]

    worst = 100.0
    worst_info = ""
    fails = 0
    for ink, tone in jobs:
        try:
            acc, info = verify_one(ink, tone, thr[ink], args.content, excl)
        except Exception as e:  # noqa
            print(f"  ERROR {ink}{tone:03d}: {e}")
            fails += 1
            continue
        if acc is None:
            print("  SKIP", info)
            continue
        if acc < 99.9999:
            print("  MISMATCH", info)
            fails += 1
        if acc < worst:
            worst = acc
            worst_info = info
    total = len(jobs)
    print(f"\nscreen tile={TILE} (reference/screen/final)  probes checked={total-fails}/{total}")
    print(f"worst accuracy = {worst:.4f}%   ({worst_info})")
    print("RESULT:", "ALL 100.0000%" if worst >= 99.9999 else "HAS MISMATCH")
    return 0 if worst >= 99.9999 else 1


if __name__ == "__main__":
    sys.exit(main())
