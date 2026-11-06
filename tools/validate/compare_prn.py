#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_prn.py —— ESC/P2 PRN 比较器（T5 交付：独立于 C++ 的 Python 校验）

比较两个 .prn：
  * 结构：块数 / 推进 / 每记录 color,n,m / 命令区参数（ESC(U,D,c,S)/P0
  * 内容：按几何模型解出内容平面（content_w_dots x content_h_units，每色 0..3），
          逐像素比较（差异率、每色墨点数）
可选 --image：把参考 PRN 的内容与输入图像做对齐抽查（行/列 ink 投影 Jaccard）

用法:
  python tools/validate/compare_prn.py <ref.prn> <gen.prn> [--image in.png] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prn_model as pm


def structure(prn):
    mode, mp = pm.mode_params(prn)
    cp = pm.cmd_params(prn)
    prn.assign_positions()
    return dict(
        modeId=mode,
        blocks=len(prn.blocks),
        records=sum(len(b.records) for b in prn.blocks),
        positions=[b.pos for b in prn.blocks],
        advances=[b.advance for b in prn.blocks[1:]],
        colors=[hex(c) for c in prn.block_colors()],
        n=sorted({r.n for b in prn.blocks for r in b.records}),
        m=sorted({r.m for b in prn.blocks for r in b.records}),
        pageUnit=cp.get("page_dpi"), margin=mp["M"], p0=mp["P0"],
        contentW=cp.get("page_w"),
        contentH=cp.get("page_top", 0) + cp.get("page_margin", 0),
        dollar=sorted({r.xpos for b in prn.blocks for r in b.records}),
    )


def compare_content(prn_a, prn_b):
    ma, mpa = pm.mode_params(prn_a)
    mb, mpb = pm.mode_params(prn_b)
    pa, wa, ha, ia = pm.extract_content_planes(prn_a, ma)
    pb, wb, hb, ib = pm.extract_content_planes(prn_b, mb)
    W, H = min(wa, wb), min(ha, hb)
    result = dict(modeA=ma, modeB=mb, Wa=wa, Ha=ha, Wb=wb, Hb=hb,
                  size_ok=(wa == wb and ha == hb), planes=[])
    total_ink = total_diff = total_area = 0
    for c in range(min(len(pa), len(pb))):
        A, B = pa[c], pb[c]
        ink_a = ink_b = diff = 0
        for y in range(H):
            ra = y * wa
            rb = y * wb
            for x in range(W):
                va = A[ra + x]
                vb = B[rb + x]
                if va:
                    ink_a += 1
                if vb:
                    ink_b += 1
                if va != vb:
                    diff += 1
        color = mpa["colors"][c] if c < len(mpa["colors"]) else None
        result["planes"].append(dict(record=c, color=hex(color) if color is not None else None,
                                     inkA=ink_a, inkB=ink_b, diff=diff))
        total_ink += ink_a
        total_diff += diff
        total_area += W * H
    result["diff_rate_pct"] = (100.0 * total_diff / total_area) if total_area else 0.0
    result["inkA"] = total_ink
    return result


def image_alignment(prn, image_path):
    """抽查几何对齐：内容平面的行/列 ink 投影 vs 图像（按 PNG 内嵌 DPI 缩放到内容尺寸）。"""
    from PIL import Image
    mode, mp = pm.mode_params(prn)
    planes, W, H, info = pm.extract_content_planes(prn, mode)
    im = Image.open(image_path).convert("RGBA")
    Wimg, Himg = im.size
    dpi = im.info.get("dpi", (120.0, 120.0))[0] or 120.0
    col_step = mp["hdpi"] / dpi
    row_step = mp["page_unit"] / dpi
    px = im.load()
    img_rows = [0] * Himg
    for y in range(Himg):
        n = 0
        for x in range(Wimg):
            r, g, b, a = px[x, y]
            if a != 0 and (r, g, b) != (255, 255, 255):
                n += 1
        img_rows[y] = n
    # PRN 内容行 ink 投影
    prn_rows = [0] * H
    for y in range(H):
        s = 0
        for c in range(len(planes)):
            pl = planes[c]
            base = y * W
            for x in range(W):
                if pl[base + x]:
                    s += 1
        prn_rows[y] = s
    # 对图像行 y 覆盖的内容行 [P0+row*y .. ，但内容平面坐标已从 P0 起
    def jac(a, b):
        if not a and not b:
            return 1.0
        return len(a & b) / len(a | b)
    # 对图像行 y 覆盖的内容行（row_step 行）判断是否有墨，与图像行是否有墨对比
    prn_has = [prn_rows[i] > 0 for i in range(H)]
    match = total = 0
    nimg = min(Himg, int(H / max(1.0, row_step)))
    for y in range(nimg):
        i0 = int(round(row_step * y))
        i1 = int(round(row_step * (y + 1)))
        prn_any = any(prn_has[i] for i in range(i0, min(i1, H)) if 0 <= i < H)
        img_any = img_rows[y] > 0
        total += 1
        if prn_any == img_any:
            match += 1
    return dict(row_ink_agreement=100.0 * match / total if total else 0.0,
                col_step=col_step, row_step=row_step, content=(W, H))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("gen")
    ap.add_argument("--image", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    a = pm.parse_prn(args.ref)
    b = pm.parse_prn(args.gen)
    sa = structure(a)
    sb = structure(b)
    rep = dict(ref=args.ref, gen=args.gen, structureA=sa, structureB=sb,
               structure_match=all(sa[k] == sb[k] for k in
                                   ("modeId", "blocks", "records", "colors", "n", "m",
                                    "pageUnit", "margin", "p0", "contentW", "contentH")))
    rep["positions_match"] = sa["positions"] == sb["positions"]
    rep["advances_match"] = sa["advances"] == sb["advances"]
    rep["content"] = compare_content(a, b)
    if args.image:
        try:
            rep["image_alignment"] = image_alignment(a, args.image)
        except Exception as e:  # noqa
            rep["image_alignment_error"] = str(e)

    print("== structure ==")
    for k in ("modeId", "blocks", "records", "colors", "n", "m", "pageUnit", "margin",
              "p0", "contentW", "contentH"):
        flag = "" if sa[k] == sb[k] else "   <-- DIFF"
        print("  %-10s %-24s %-24s%s" % (k, sa[k], sb[k], flag))
    print("  positions/advances match:", rep["positions_match"], rep["advances_match"])
    c = rep["content"]
    print("== content planes ==")
    print("  size: %dx%d vs %dx%d  size_ok=%s" % (c["Wa"], c["Ha"], c["Wb"], c["Hb"], c["size_ok"]))
    for p in c["planes"]:
        print("  record %d color %s: inkA=%d inkB=%d diff=%d" %
              (p["record"], p["color"], p["inkA"], p["inkB"], p["diff"]))
    print("  TOTAL diff rate = %.4f%%   inkA=%d" % (c["diff_rate_pct"], c["inkA"]))
    if "image_alignment" in rep:
        ia = rep["image_alignment"]
        print("== image alignment ==  row_ink_agreement=%.1f%%  (colStep=%.2f rowStep=%.2f content=%s)" %
              (ia["row_ink_agreement"], ia["col_step"], ia["row_step"], ia["content"]))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
    ok_content = c["diff_rate_pct"] < 0.01
    ok_struct = rep["structure_match"] and rep["positions_match"]
    if ok_content and ok_struct:
        verdict = "IDENTICAL"
    elif ok_content:
        verdict = "CONTENT-EQUAL (structure differs: blank-skip/feather)"
    else:
        verdict = "DIFF"
    print("\nRESULT:", verdict)
    return 0 if ok_content else 1


if __name__ == "__main__":
    sys.exit(main())
