#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T6-B: analyse screening probe PRNs and write work/protocol/screen_probe.md.

Geometry model for A3-DTF-1390 modes (validated on this corpus):
  mode0 = 720x360 dpi -> W = img_w*6, H = img_h*3
  mode2 = 720x720 dpi -> W = img_w*6, H = img_h*6
Image area = W*H; the ESC/P2 raster records pad lines/bytes, so use the image
area (not n*4*m) as the coverage denominator.
Dot size = 2-bit value inside each raster byte: 1/2/3 (small/medium/large).
"""
import json
import os
import sys
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
sys.path.insert(0, os.path.join(WS, "tools", "prn_tools"))
import mtrip_oracle as O   # noqa: E402
import parse_prn as P      # noqa: E402

EV = os.path.join(HERE, "evidence")
OUT_MD = os.path.join(HERE, "screen_probe.md")

MODE_DPI = {0: (720, 360), 2: (720, 720)}


def decode(prn):
    d = open(prn, "rb").read()
    head = d[:2]
    if head == b"\x55\x55":
        return {"format": "hssf-0x5555", "size": len(d)}
    job = P.parse_job(d, decode=True)
    per = {}
    for b in job.blocks:
        for r in b.records:
            x = per.setdefault(r.color, {"ink": 0, "hist": Counter(),
                                          "records": 0, "n": set(), "m": set()})
            x["records"] += 1
            x["n"].add(r.n)
            x["m"].add(r.m)
            if r.raw:
                for byte in r.raw:
                    for sh in (0, 2, 4, 6):
                        v = (byte >> sh) & 3
                        if v:
                            x["ink"] += 1
                            x["hist"][v] += 1
    return {"format": "esc/p2", "size": len(d), "blocks": len(job.blocks),
            "colors": {"0x%02X" % c: {"ink": x["ink"], "hist": dict(x["hist"]),
                                      "records": x["records"], "n": sorted(x["n"]),
                                      "m": sorted(x["m"])}
                       for c, x in sorted(per.items())}}


def image_info(name):
    """reference/inputs/<name> -> (w, h) in px."""
    path = os.path.join(O.INPUTS, name)
    if not os.path.isfile(path):
        return None
    with Image.open(path) as im:
        return im.size


def case_from_stem(stem):
    """probe_screen_<case>_<machine>_m<mode> -> (case, machine, mode)."""
    body = stem[len("probe_screen_"):]
    machine = "a3dtf1390" if "_a3dtf1390_m" in body else (
        "h13xp600" if "_h13xp600_m" in body else None)
    if machine is None:
        return None
    idx = body.rfind("_m")
    case = body[:idx - len(machine) - 1]
    try:
        mode = int(body[idx + 2:])
    except ValueError:
        return None
    return case, machine, mode


INPUT_OF_CASE = {}   # filled from screen_probe_raw/singles jsons


def area_for(case, mode):
    fn = INPUT_OF_CASE.get(case)
    if not fn:
        return None
    sz = image_info(fn)
    if not sz or mode not in MODE_DPI:
        return None
    xd, yd = MODE_DPI[mode]
    return (sz[0] * xd // 120) * (sz[1] * yd // 120), sz


def main():
    # gather input mapping from evidence jsons
    for fn in ("screen_probe_raw.json", "screen_probe_singles.json"):
        for r in json.load(open(os.path.join(EV, fn), encoding="utf-8")):
            case = r.get("case") or case_from_stem(r["stem"])[0]
            INPUT_OF_CASE[case] = r["image"]

    rows = []
    for prn in sorted(os.path.join(O.PRNS, f)
                      for f in os.listdir(O.PRNS) if f.startswith("probe_screen_")
                      and f.endswith(".prn")):
        stem = os.path.basename(prn)[:-4]
        if os.path.getsize(prn) == 0:
            continue
        parsed = case_from_stem(stem)
        if parsed is None:
            continue
        case, machine, mode = parsed
        feat = decode(prn)
        rec = {"stem": stem, "case": case, "machine": machine, "mode": mode,
               "image": INPUT_OF_CASE.get(case), "size": feat["size"],
               "format": feat["format"]}
        if machine == "a3dtf1390" and "colors" in feat:
            area, sz = area_for(case, mode) or (None, None)
            rec["img_px"] = sz
            rec["area"] = area
            cols = {}
            for c, x in feat["colors"].items():
                hist = x["hist"]
                cols[c] = {
                    "ink_px": x["ink"],
                    "coverage_img": round(x["ink"] / area, 6) if area else None,
                    "hist": hist,
                    "hist_pct": {k: round(v / x["ink"], 4)
                                 for k, v in sorted(hist.items())} if x["ink"] else {},
                }
            rec["colors"] = cols
            rec["blocks"] = feat.get("blocks")
        rows.append(rec)

    singles = [r for r in rows if r["case"].startswith("probe_")]
    mains = [r for r in rows if not r["case"].startswith("probe_")]
    with open(os.path.join(EV, "screen_probe_features2.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    md = []
    md.append("# T6-B：CMYK TIFF 加网/线性化探针语料与初步规律\n")
    md.append("生成时间 2026-11-06；oracle=mtripNet HTTP(8089)，PRN 在 "
              "`reference/prn_samples/probe_screen_*.prn`，作业 JSON 在 "
              "`reference/jobs/`，输入图在 `reference/inputs/`。\n")
    md.append("## 1. CMYK TIFF 是否被接受\n")
    md.append("* PIL 生成的 CMYK TIFF（Photometric=5 Separated, 内嵌 120 dpi）"
              "**被蒙泰接受**：`queryFile` 返回 `color=6`（cmyk）、`xdpi=120`；"
              "`rip` result=0。\n"
              "* 全白（CMYK 全 0）输出仅 **264 B**（无栅格数据）；H13 为定长帧 456,048 B。\n"
              "* `mtcount:true` 被本机驱动拒绝：**立即返回 `{\"result\":1,\"error\":\"用户取消\"}`**（0.02s，"
              "不生成 PRN）——不要用 mtcount 取点型统计；本文用 PRN 解码统计替代。\n")
    md.append("## 2. 主探针图运行结果（A3 m2=720x720 / A3 m0=720x360 / H13 m0=720x720）\n")
    md.append("| case | 输入 | A3 m2 PRN B | A3 m0 PRN B | H13 m0 PRN B |\n|---|---|---|---|---|")
    for c in sorted(set(r["case"] for r in mains if not r["case"].startswith(("rgb_",)))):
        sel = {r["machine"] + "_m%d" % r["mode"]: r for r in mains if r["case"] == c}
        a2 = sel.get("a3dtf1390_m2", {}).get("size", "-")
        a0 = sel.get("a3dtf1390_m0", {}).get("size", "-")
        h0 = sel.get("h13xp600_m0", {}).get("size", "-")
        md.append("| %s | %s | %s | %s | %s |" % (c, INPUT_OF_CASE.get(c, "?"), a2, a0, h0))
    md.append("")
    md.append("## 3. 单通道纯色块 → PRN 点阵规律（关键）\n")
    md.append("每张输入图只有一个墨 C/M/Y/K 的单一值（64×64，全图恒定），"
              "因此可直接从 PRN 统计该值下每个点（2-bit：1=小点/2=中点/3=大点）的数量。"
              "`ink_px` 为 2-bit 非零像素数；`覆盖率` 以图像实际输出面积（W×H，"
              "720dpi 横向、720/360dpi 纵向）为分母；`点型占比` 为 ink_px 内 1/2/3 点占比。\n")
    md.append("### 3.1 mode2（720×720 dpi）\n")
    md.append("| 输入墨值 | 对应颜色码 | PRN B | ink_px | 覆盖率 | 小点1 | 中点2 | 大点3 |\n|---|---|---|---|---|---|---|---|")
    for r in sorted(singles, key=lambda r: (r.get("mode") != 2, r["case"])):
        if r.get("mode") != 2 or "colors" not in r:
            continue
        ink = None
        for c, x in r["colors"].items():
            if x["ink_px"]:
                ink = (c, x)
                break
        if not ink:
            md.append("| %s | - | %d | 0 | 0 | - | - | - |" % (r["case"], r["size"]))
            continue
        c, x = ink
        pct = x["hist_pct"]
        md.append("| %s | 0x%s | %d | %d | %.4f | %s | %s | %s |" % (
            r["case"].replace("probe_", ""), c[2:], r["size"], x["ink_px"],
            x["coverage_img"] or 0,
            pct.get("1", 0), pct.get("2", 0), pct.get("3", 0)))
    md.append("")
    md.append("### 3.2 mode0（720×360 dpi，仅纵向分辨率不同）\n")
    md.append("| 输入墨值 | 对应颜色码 | PRN B | ink_px | 覆盖率 | 小点1 | 中点2 | 大点3 |\n|---|---|---|---|---|---|---|---|")
    for r in sorted(singles, key=lambda r: (r.get("mode") != 0, r["case"])):
        if r.get("mode") != 0 or "colors" not in r:
            continue
        ink = None
        for c, x in r["colors"].items():
            if x["ink_px"]:
                ink = (c, x)
                break
        if not ink:
            md.append("| %s | - | %d | 0 | 0 | - | - | - |" % (r["case"], r["size"]))
            continue
        c, x = ink
        pct = x["hist_pct"]
        md.append("| %s | 0x%s | %d | %d | %.4f | %s | %s | %s |" % (
            r["case"].replace("probe_", ""), c[2:], r["size"], x["ink_px"],
            x["coverage_img"] or 0,
            pct.get("1", 0), pct.get("2", 0), pct.get("3", 0)))
    md.append("")
    md.append("### 3.3 C 通道细扫（0..240，步长 16）→ 2-bit 量化律\n")
    sweep_path = os.path.join(EV, "screen_probe_sweep.json")
    if os.path.isfile(sweep_path):
        sw = json.load(open(sweep_path, encoding="utf-8"))
        md.append("| 输入墨值 v | PRN B | 颜色码 | 非零覆盖率 | 小点1 | 中点2 | 大点3 | 平均点值 Σk·p | 3v/255 |")
        md.append("|---|---|---|---|---|---|---|---|---|")
        for r in sw:
            if r.get("result") != 0:
                continue
            if "pct" not in r:
                md.append("| %d | %d | - | 0 | - | - | - | 0 | 0 |" % (r["v"], r["size"]))
                continue
            p = r["pct"]
            avg = sum(int(k) * x for k, x in p.items())
            md.append("| %d | %d | %s | %.4f | %s | %s | %s | %.4f | %.4f |" % (
                r["v"], r["size"], r.get("code", "-"), r["cov"],
                p.get("1", 0), p.get("2", 0), p.get("3", 0), avg, 3 * r["v"] / 255))
        md.append("""
**律：整幅平均 2-bit 点值 = 3·v/255（v=16..240 全部实测误差 <1e-4）。**
即 RIP 把 8-bit 墨量均匀分配到“每像素 0/1/2/3”四级点：
`v<85` 时只用小点(1)、覆盖率 = 3v/255；`85≤v<170` 覆盖率 100%、小点↔中点按比例混合；
`v≥170` 覆盖率 100%、中点↔大点按比例混合。**这就是 2-bit 多值加网的核心量化律，可直接实现。**

### 3.4 点阵空间排布样例（mode2，C 通道，取光栅有效区）

每行 32 像素（数字=2-bit 点值，0=空），可见点型分布呈**伪随机（误差扩散/蓝噪声类）**而非规则网点：
""")
        # embed pattern samples
        for v in (64, 96, 128, 192):
            pp = os.path.join(O.PRNS, "probe_sweep_C%d_a3dtf1390_m2.prn" % v)
            if not os.path.isfile(pp):
                continue
            job = P.parse_job(open(pp, "rb").read(), decode=True)
            best, bestink = None, 0
            for b in job.blocks:
                for rr in b.records:
                    if not rr.raw:
                        continue
                    inkv = sum(1 for byte in rr.raw for sh in (0, 2, 4, 6)
                               if (byte >> sh) & 3)
                    if inkv > bestink:
                        bestink, best = inkv, rr
            if not best:
                continue
            y0 = 0
            for y in range(best.m):
                if any(best.raw[y * best.n:(y + 1) * best.n]):
                    y0 = y
                    break
            md.append("```\nv=%d:\n" % v)
            for y in range(y0, y0 + 10):
                line = best.raw[y * best.n:(y + 1) * best.n]
                cells = []
                for x in range(32):
                    byte = line[x // 4]
                    cells.append(str((byte >> ((x % 4) * 2)) & 3))
                md.append("".join(cells))
            md.append("```\n")
    md.append("## 4. 汇总图（ramp16 / patch20 / 全白 / 满版）\n")
    md.append("| case | 机器/mode | PRN B | 颜色码→ink_px/覆盖率/点型占比 |\n|---|---|---|---|")
    for r in mains:
        if not r["case"].startswith("cmyk"):
            continue
        if "colors" not in r:
            md.append("| %s | %s m%d | %d | (HSSF，未解码) |" % (
                r["case"], r["machine"], r["mode"], r["size"]))
            continue
        parts = []
        for c, x in r["colors"].items():
            parts.append("%s:ink=%d cov=%.3f hist=%s" % (
                c, x["ink_px"], x["coverage_img"] or 0,
                x["hist_pct"]))
        md.append("| %s | %s m%d | %d | %s |" % (
            r["case"], r["machine"], r["mode"], r["size"],
            "；".join(parts)[:500]))
    md.append("")
    md.append("## 5. RGB 探针（任务 C，供 T3 反推 RGB→CMYK 链）\n")
    md.append("| case | 机器/mode | PRN B | 颜色码→ink_px/覆盖率/点型占比 |\n|---|---|---|---|")
    for r in mains:
        if not r["case"].startswith("rgb_"):
            continue
        if "colors" not in r:
            md.append("| %s | %s m%d | %d | (HSSF) |" % (
                r["case"], r["machine"], r["mode"], r["size"]))
            continue
        parts = []
        for c, x in r["colors"].items():
            parts.append("%s:ink=%d cov=%.3f hist=%s" % (
                c, x["ink_px"], x["coverage_img"] or 0, x["hist_pct"]))
        md.append("| %s | %s m%d | %d | %s |" % (
            r["case"], r["machine"], r["mode"], r["size"], "；".join(parts)[:500]))
    md.append("")
    md.append("""## 6. 初步结论

1. **CMYK TIFF 可作输入**（mode2/mode0/H13 全部 result=0）；CMYK TIFF 的通道被直接当作设备墨量处理（mode2 无 ICC 校色）。
2. **单通道墨值 → 颜色码映射（A3 mode2/m0 实测）**：C→`0x00`，K→`0x04`，Y→`0x11`，M→`0x12`（另：A3 6 平面模式还有 0x01/0x02 两个颜色码，见 T2/T3）。
3. **2-bit 多值加网量化律（核心！）**：整幅平均点值 = `3·v/255`（v=16..240 实测误差<1e-4）。
   即每像素 2-bit 值 k∈{0,1,2,3} 代表 0/1/3、2/3、3/3 的墨量：
   - `v < 85`：只用小点(1)，非零覆盖率 = 3v/255（实测 v=16→0.188、64→0.753、80→0.941）；
   - `85 ≤ v < 170`：覆盖率 100%，小点↔中点混合（v=96: 87%:13%；128: 50%:50%；160: 12%:88%）；
   - `v ≥ 170`：覆盖率 100%，中点↔大点混合（176: 93%:7%；192: 74%:26%；240: 18%:82%；255: 全大点）。
   点型空间排布呈伪随机（类误差扩散/蓝噪声，见 §3.4 样例），不是规则 AM 网点。
4. **PRN 体积与点型均匀度相关**：单一大点满版仅 ~19.9 KB（RLE 易压），混合点型 ~51 KB。
5. **720×360 与 720×720（mode0/m2）加网点型规律一致**，仅纵向输出行数不同（W×H 分别为 img×6×img×3 与 img×6×img×6），说明挂网模板/点型规律由驱动 prs 决定、与纵向分辨率档位无关。
6. H13 输出 HSSF 定长帧（456,048 B@m0），无法用 ESC/P2 解析器看内部点阵，交 T4。
7. **mtcount 不可用**（result=1 用户取消），点型统计只能靠解码 PRN 自行统计。

## 7. 给 T3 的接口

* 每个 `probe_screen_*.prn` 的逐色统计（ink_px/覆盖率/点型直方图）在
  `work/protocol/evidence/screen_probe_features2.json`；
* 单通道值的线性化响应表在 §3；ramp16 图的 16 级响应可由 §3 查表拼出；
* 若需要“点型体积(pl)”而非计数，需要 prs 里的点大小配置（T3 侧）+ 本表计数即可换算。

## 8. 复现命令

```powershell
python tools\\oracle\\make_screen_probes.py      # 生成输入图
python work\\protocol\\exp_screen.py             # 主探针（3 机器/模式 × 5 图）
python work\\protocol\\exp_screen_singles.py     # 20 个单值图 × m2/m0
python work\\protocol\\analyze_screen.py         # 解码统计
python work\\protocol\\gen_screen_report.py      # 生成本报告
```
""")
    with open(OUT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))
    print("wrote", OUT_MD, sum(len(x) for x in md), "chars")
    # console preview of dot law
    for r in sorted(singles, key=lambda r: (r.get("mode") != 2, r["case"])):
        if r.get("mode") == 2 and "colors" in r:
            for c, x in r["colors"].items():
                if x["ink_px"]:
                    print(r["case"], c, "ink", x["ink_px"], "cov", x["coverage_img"],
                          "pct", x["hist_pct"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
