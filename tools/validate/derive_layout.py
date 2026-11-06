#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
derive_layout.py -- 从蒙泰参考语料反推 ESC/P2 版面布局规律 (T5)

分析内容：
  1. 块的 advance 序列 / 位置 / 块数
  2. 光栅行 -> 页面行映射（row_step）
  3. 内容在页面上的起点 P0 与缩放（用已知输入图）
  4. 重叠带（同一 page_row 被多个块覆盖）的拆分规则
  5. 水平映射（x = colOffset + colScale * img_x）与 n 的取值
  6. 各 ESC 命令字段与内容宽高 / modeId 的关系

用法:
  python derive_layout.py <prn> [--step N] [--accum]
"""
from __future__ import annotations

import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prn_model as pm


def summary(prn, step=None):
    cp = pm.cmd_params(prn)
    print("== %s (%d B)" % (os.path.basename(prn.path), prn.size))
    print("   mode params:", {k: cp.get(k) for k in
                             ("unit", "page_dpi", "v_dpi", "h_dpi", "raster_r",
                              "raster_v", "raster_h", "raster_v_dpi", "raster_h_dpi",
                              "page_margin", "page_top", "page_w", "page_h", "dotsize")})
    init = prn.assign_positions()
    nblocks = len(prn.blocks)
    advs = [b.advance for b in prn.blocks[1:]]
    print("   blocks=%d initial=%d advances=%s" % (nblocks, init, collections.Counter(advs).most_common(6)))
    if not prn.blocks:
        return
    recs0 = prn.blocks[0].records
    print("   records/block=%d colors=%s n=%s m=%s comp/bit=%s" % (
        len(recs0), [hex(r.color) for r in recs0], sorted({r.n for b in prn.blocks for r in b.records}),
        sorted({r.m for b in prn.blocks for r in b.records}),
        sorted({(r.comp, r.bit) for b in prn.blocks for r in b.records})))
    # ESC($ 参数分布
    print("   ESC($ xpos:", collections.Counter(r.xpos for b in prn.blocks for r in b.records).most_common(6))
    if step is None:
        step = cp["page_dpi"] // cp["raster_v_dpi"]
    print("   row_step = %d (page %d / raster_v %d)" % (step, cp["page_dpi"], cp["raster_v_dpi"]))
    # 每色墨量 / 页面行范围
    for c in prn.block_colors():
        tot = 0
        pm_rows = []
        xmin, xmax = 1 << 30, -1
        vals = collections.Counter()
        for b in prn.blocks:
            rec = prn.records_of(b.index, c)
            if rec is None or not rec.raw:
                continue
            for r in range(rec.m):
                line = rec.raw[r * rec.n:(r + 1) * rec.n]
                if not any(line):
                    continue
                pm_rows.append(b.pos + step * r)
                for byi, byte in enumerate(line):
                    if not byte:
                        continue
                    xmin = min(xmin, byi * 4)
                    xmax = max(xmax, byi * 4 + 3)
                    for k in range(4):
                        v = (byte >> (6 - 2 * k)) & 3
                        if v:
                            vals[v] += 1
                            tot += 1
        print("   color %02x: dots=%d rows p=[%s..%s] x=[%s..%s] levels=%s" % (
            c, tot, min(pm_rows) if pm_rows else None, max(pm_rows) if pm_rows else None,
            xmin, xmax, dict(vals)))


def overlap_analysis(prn, step=None, max_rows=12):
    cp = pm.cmd_params(prn)
    if step is None:
        step = cp["page_dpi"] // cp["raster_v_dpi"]
    init = prn.assign_positions()
    cover = prn.row_cover(step)
    multi = sorted(p for p, v in cover.items() if len(v) > 1)
    print("\n-- overlap: %d multi-covered page rows, range %s..%s" % (
        len(multi), multi[0] if multi else None, multi[-1] if multi else None))
    # 每个重叠行的覆盖块数分布
    print("   cover count histogram:", collections.Counter(len(cover[p]) for p in multi).most_common(8))
    for p in multi[:max_rows]:
        entries = cover[p]
        print("   p=%d covered by %s" % (p, entries))
        for c in prn.block_colors():
            masks = []
            for (bi, r) in entries:
                rec = prn.records_of(bi, c)
                if rec is None:
                    masks.append({})
                    continue
                line = rec.raw[r * rec.n:(r + 1) * rec.n]
                m = {}
                for byi, byte in enumerate(line):
                    for k in range(4):
                        v = (byte >> (6 - 2 * k)) & 3
                        if v:
                            m[byi * 4 + k] = v
                masks.append(m)
            if not masks or all(not m for m in masks):
                continue
            # 两两交集
            info = []
            for i in range(len(masks)):
                for j in range(i + 1, len(masks)):
                    both = set(masks[i]) & set(masks[j])
                    info.append("%d&%d: both=%d (|A|=%d,|B|=%d)" % (
                        entries[i][0], entries[j][0], len(both), len(masks[i]), len(masks[j])))
            # x 奇偶
            par = []
            for i, m in enumerate(masks):
                xs = sorted(m)
                if xs:
                    par.append("%s: x%%2=%s x%%4=%s" % (
                        entries[i][0],
                        dict(collections.Counter(x % 2 for x in xs)),
                        dict(collections.Counter(x % 4 for x in xs))))
            print("     %02x %s" % (c, " ; ".join(info)))
            for line in par:
                print("        ", line)
            # 打印前 64 dot 的归属模式
            pat = []
            for x in range(0, 64):
                who = ""
                for i, m in enumerate(masks):
                    if x in m:
                        who += str(entries[i][0])
                pat.append(who if who else ".")
            print("        x0..63:", "|".join(pat))


def main(argv):
    step = None
    if "--step" in argv:
        i = argv.index("--step")
        step = int(argv[i + 1])
        del argv[i:i + 2]
    paths = [a for a in argv[1:] if not a.startswith("--")]
    for p in paths:
        prn = pm.parse_prn(p)
        summary(prn, step)
        if prn.blocks:
            overlap_analysis(prn, step)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
