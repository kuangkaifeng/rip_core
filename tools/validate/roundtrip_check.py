#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
roundtrip_check.py —— T5 验收驱动（ESC/P2 版面+编码器闭环验证）

流程（每个样本）：
  1) build/mtr_prncheck.exe roundtrip <ref.prn> --out <out.prn> --mode N
     （C++ 反解 -> 内容平面 -> layout_escp2 + escp2_writer 重新编码）
  2) build/mtr_prncheck.exe compare <ref.prn> <out.prn>
     （结构/内容平面/页面 raster 差异率）
  3) 汇总：白图样本要求逐字节一致；其余要求内容平面差异率 = 0%（几何闭环）

用法: python tools/validate/roundtrip_check.py [--exe build/mtr_prncheck.exe]
"""
import os
import re
import subprocess
import sys

WS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXE = os.path.join(WS, "build", "mtr_prncheck.exe")
OUT = os.path.join(WS, "tools", "validate", "out")
PRN = os.path.join(WS, "reference", "prn_samples")

# 验收目标（T5）：(样本, mode, 期望)
TARGETS = [
    # 纯白：整文件应逐字节一致（TI 由参考 PRN 复制，因此应 0 差异）
    ("a3dtf1390_flat_white_100_m2.prn", 2, "byte_exact"),
    ("a3dtf1390_flat_white_100_m0.prn", 0, "byte_exact"),
    ("a3dtf1390_flat_white_100_m1.prn", 1, "byte_exact"),
    ("a3dtf1390_flat_white_100_m3.prn", 3, "byte_exact"),
    # 内容图：几何闭环 = 内容平面差异率 0%
    ("a3dtf1390_flat_black_100_m2.prn", 2, "raster_equal"),
    ("a3dtf1390_flat_black_100_m0.prn", 0, "raster_equal"),
    ("a3dtf1390_flat_black_100_m1.prn", 1, "raster_equal"),
    ("a3dtf1390_flat_black_100_m3.prn", 3, "raster_equal"),
    ("a3dtf1390_checker_1px_100_m2.prn", 2, "raster_equal"),
    ("a3dtf1390_checker_8px_720_m2.prn", 2, "raster_equal"),
    ("geom_flat_black_720_m2.prn", 2, "raster_equal"),
    ("probe_black_64_m2_golden.prn", 2, "raster_equal"),
    ("golden_repro_1793946733280.prn", 2, "raster_equal"),
]


def run(args):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def parse_report(text):
    rep = {}
    m = re.search(r"blocks: (\d+) vs (\d+)", text)
    if m:
        rep["blocks_ref"], rep["blocks_gen"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"content: (\d+)x(\d+) vs (\d+)x(\d+)", text)
    if m:
        rep["size"] = tuple(int(x) for x in m.groups())
    m = re.search(r"TOTAL pixel diff rate = ([\d.]+)%", text)
    if m:
        rep["diff_pct"] = float(m.group(1))
    m = re.search(r"commonDiff=(\d+) firstDiff=0x([0-9a-f-]+)", text)
    if m:
        rep["byte_diff"] = int(m.group(1))
        rep["first_diff"] = m.group(2)
    return rep


def test_cli_white():
    """端到端：mtr_cli rip 生成纯白作业，与 oracle 逐字节比较（仅 TI 时间允许不同）。
    TI 数据位于 remote 段偏移 45..52（tag 0x29 + 4），归一化后应完全一致。
    """
    cli = os.path.join(WS, "build", "mtr_cli.exe")
    prs = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\A3-DTF-1390.prs"
    ref = os.path.join(PRN, "a3dtf1390_flat_white_100_m2.prn")
    img = os.path.join(WS, "reference", "inputs", "flat_white_100.png")
    out = os.path.join(OUT, "cli_white_100_m2.prn")
    if not (os.path.exists(cli) and os.path.exists(prs)):
        return None, "cli/prs missing"
    p = subprocess.run([cli, "rip", "--input", img, "--prn", out, "--prs", prs, "--mode", "2"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not os.path.exists(out):
        return False, (p.stdout + p.stderr)[-300:]
    a = open(ref, "rb").read()
    b = open(out, "rb").read()
    TI = range(45, 53)
    diffs = [i for i in range(min(len(a), len(b)))
             if a[i] != b[i] and i not in TI]
    size_ok = (len(a) == len(b))
    return (size_ok and not diffs), "ref=%dB gen=%dB nonTI_diff=%d %s" % (
        len(a), len(b), len(diffs), ("first=0x%x" % diffs[0]) if diffs else "TI-only")


def main():
    exe = EXE
    if "--exe" in sys.argv:
        exe = sys.argv[sys.argv.index("--exe") + 1]
    if not os.path.exists(exe):
        print("missing exe:", exe)
        return 2
    os.makedirs(OUT, exist_ok=True)
    rows = []
    ok_all = True
    for name, mode, expect in TARGETS:
        ref = os.path.join(PRN, name)
        if not os.path.exists(ref):
            rows.append((name, mode, expect, "MISSING", None))
            ok_all = False
            continue
        out = os.path.join(OUT, name + ".regen.prn")
        rc, txt = run([exe, "roundtrip", ref, "--out", out, "--mode", str(mode)])
        rep = parse_report(txt)
        rc2, txt2 = run([exe, "compare", ref, out])
        rep2 = parse_report(txt2)
        rep.update(rep2)
        if expect == "byte_exact":
            ok = rep.get("byte_diff") == 0
        else:
            ok = rep.get("diff_pct") is not None and rep["diff_pct"] < 0.01
        ok_all = ok_all and ok
        rows.append((name, mode, expect, "OK" if ok else "FAIL", rep))

    print("%-40s %4s %-12s %5s %s" % ("sample", "mode", "expect", "res", "detail"))
    for name, mode, expect, res, rep in rows:
        detail = ""
        if rep:
            detail = ("blocks %s->%s, size %s, contentDiff=%s%%, byteDiff=%s"
                      % (rep.get("blocks_ref"), rep.get("blocks_gen"), rep.get("size"),
                         rep.get("diff_pct"), rep.get("byte_diff")))
        print("%-40s %4s %-12s %5s %s" % (name, mode, expect, res, detail))

    cli_ok, cli_detail = test_cli_white()
    print("%-40s %4s %-12s %5s %s" % ("[CLI] flat_white_100 m2 (TI-normalized)",
                                      "2", "byte_exact", "OK" if cli_ok else "FAIL", cli_detail))
    if cli_ok is None:
        ok_all = False
    elif not cli_ok:
        ok_all = False

    print("\nRESULT:", "ALL OK" if ok_all else "FAILED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
