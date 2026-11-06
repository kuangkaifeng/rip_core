#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_rerun_determinism.py —— 独立复核 protocol-analyst 的"蒙泰 PRN 确定性"结论。

对 52 个异常探针（13 tone × C/M/Y/K）的原始 + 重跑 r1/r2：
  1) PRN 字节比较：TI 时间戳 7 字节归一化后应完全一致；
  2) 内容平面比较（mtr_prncheck content，C++ 解码器）：三份应 0 像素差异；
  3) 审计 832 个 cell（work/prs/oracle_screen_audit.json）：
     三份在该 (tone, 像素) 的 level 应全为 0（确定性漏点）。

用法: python tools/validate/verify_rerun_determinism.py
"""
from __future__ import annotations

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
RERUN = os.path.join(PRN, "rerun")
AUDIT = os.path.join(WS, "work", "prs", "oracle_screen_audit.json")
TILE = 1024
INK_RECORD = {"K": (0, 0x04), "C": (1, 0x00), "M": (2, 0x12), "Y": (3, 0x11)}


def prn_path(ink, tone, suffix=""):
    base = f"probe_scan_{ink}{tone:03d}_176_a3dtf1390_m2"
    if suffix:
        return os.path.join(RERUN, base + suffix + ".prn")
    return os.path.join(PRN, base + ".prn")


def load_audit():
    audit = json.load(open(AUDIT, encoding="utf-8"))
    cells = {}          # ink -> {'x,y': [tone,...]}
    for ink, poss in audit.items():
        for key, lst in poss.items():
            cells.setdefault(ink, {})[key] = [int(c[0]) for c in lst]
    return cells


def byte_equal_ignoring_ti(paths):
    """返回 (ok, size, ndiff, firstdiff)。TI 数据在 remote 段偏移 45..52。"""
    bufs = [open(p, "rb").read() for p in paths]
    n = min(len(b) for b in bufs)
    diffs = []
    for i in range(n):
        if 45 <= i <= 52:      # TI: tag 0x29 + 4 -> data 45..52，平均无需比较
            continue
        vals = {b[i] for b in bufs}
        if len(vals) > 1:
            diffs.append(i)
    size_ok = len({len(b) for b in bufs}) == 1
    return size_ok and not diffs, [len(b) for b in bufs], len(diffs), (diffs[0] if diffs else -1)


def decode_plane(prn_path, ink, tmpdir):
    subprocess.run([EXE, "content", prn_path, "--mode", "2", "--out", tmpdir],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    rec, code = INK_RECORD[ink]
    hit = glob.glob(os.path.join(tmpdir, f"content_{rec}_{code:02x}.w*.bin"))
    if not hit:
        return None, 0, 0
    base = os.path.basename(hit[0])
    W, H = (int(v) for v in base.split(".w")[1].split(".bin")[0].split("h"))
    return open(hit[0], "rb").read(), W, H


def main():
    if not os.path.exists(EXE):
        print("missing exe:", EXE)
        return 2
    audited = load_audit()
    tones = sorted({t for ink in audited for lst in audited[ink].values() for t in lst})
    print(f"audit tones ({len(tones)}): {tones}")

    fail = 0
    probes = 0
    byte_ok_cnt = 0
    plane_ok_cnt = 0
    cells_checked = 0
    cells_ok = 0
    for ink in ("C", "M", "Y", "K"):
        for tone in tones:
            probes += 1
            p0 = prn_path(ink, tone)
            p1 = prn_path(ink, tone, "_r1")
            p2 = prn_path(ink, tone, "_r2")
            if not (os.path.exists(p0) and os.path.exists(p1) and os.path.exists(p2)):
                print(f"  SKIP {ink}{tone:03d}: missing files")
                fail += 1
                continue
            # 1) 字节比较（TI 归一化）
            ok, sizes, nd, first = byte_equal_ignoring_ti([p0, p1, p2])
            if ok:
                byte_ok_cnt += 1
            else:
                print(f"  BYTE-DIFF {ink}{tone:03d}: sizes={sizes} ndiff={nd} first=0x{first:x}")
                fail += 1
            # 2) 内容平面比较
            tmp = tempfile.mkdtemp(prefix="mtrdet_")
            try:
                pa, Wa, Ha = decode_plane(p0, ink, tmp)
                tmp2 = tempfile.mkdtemp(prefix="mtrdet2_")
                try:
                    pb, Wb, Hb = decode_plane(p1, ink, tmp2)
                finally:
                    shutil.rmtree(tmp2, ignore_errors=True)
                tmp3 = tempfile.mkdtemp(prefix="mtrdet3_")
                try:
                    pc, Wc, Hc = decode_plane(p2, ink, tmp3)
                finally:
                    shutil.rmtree(tmp3, ignore_errors=True)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            if pa is None or pb is None or pc is None:
                print(f"  PLANE-MISSING {ink}{tone:03d}")
                fail += 1
                continue
            if pa == pb == pc:
                plane_ok_cnt += 1
            else:
                nd = sum(1 for x, y in zip(pa, pb) if x != y) + sum(1 for x, y in zip(pa, pc) if x != y)
                print(f"  PLANE-DIFF {ink}{tone:03d}: ndiff={nd}")
                fail += 1
            # 3) 审计 cell level 检查（三份均为 0）
            W = Wa
            for key, cell_tones in audited[ink].items():
                if tone not in cell_tones:
                    continue
                y, x = (int(v) for v in key.split(","))
                cells_checked += 1
                lv = (pa[y * W + x], pb[y * W + x], pc[y * W + x])
                if lv == (0, 0, 0):
                    cells_ok += 1
                else:
                    print(f"  CELL-NONZERO {ink}{tone:03d} ({x},{y}): {lv}")
                    fail += 1

    print(f"\nprobes: {probes}  byte-identical(TI-normalized): {byte_ok_cnt}  "
          f"content-plane-identical: {plane_ok_cnt}")
    print(f"audit cells checked: {cells_checked}  all-zero across orig/r1/r2: {cells_ok}")
    print("RESULT:", "DETERMINISTIC (non-monotonic oracle cells reproducible)"
          if fail == 0 else f"HAS {fail} FAILURES")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
