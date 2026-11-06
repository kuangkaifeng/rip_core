#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T6-A: render markdown tables from work/protocol/icc_mode_map.json.

Output: work/protocol/icc_table.md  (to be pasted into docs/maintop_api.md §12)
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "icc_mode_map.json"), encoding="utf-8"))
out = []

qmk = {"a3dtf1390": "A3-DTF-1390.prs", "h13xp600": "H13 XP600.prs"}

for key in ("a3dtf1390", "h13xp600"):
    out.append("#### %s（`%s`）\n" % (
        "A3-DTF-1390（改装机，ESC/P2）" if key == "a3dtf1390"
        else "H13 XP600（板卡机，HSSF）", qmk[key]))
    out.append("| modeId | dpi | planes | ink | colorCorrection | 输出 destCmyk ICC | srcCmyk ICC | srcRgb ICC | channelMax(K,C,M,Y[,W1,W2]) | dotGain | sepLightType |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for m, entry in sorted(d["modes"][key].items(), key=lambda kv: int(kv[0])):
        qm = entry.get("queryMode") or {}
        s = entry.get("summary") or {}
        if s.get("result") == 0:
            mcm = s.get("mcm") or {}
            h = s.get("header") or {}
            out.append("| %s | %s | %s | %s | %s | `%s` | `%s` | `%s` | %s | %s | %s |" % (
                m, qm.get("dpi", ""), qm.get("planes", ""), qm.get("ink", ""),
                qm.get("colorCorrection"),
                mcm.get("destCmykPath", "?"), mcm.get("srcCmykPath", "?"),
                mcm.get("srcRgbPath", "?"),
                h.get("channelMax", "?"), h.get("dotGain", "?"),
                h.get("sepLightType", "?")))
        else:
            out.append("| %s | %s | %s | %s | %s | —（返回 0x%08X：%s） | — | — | — | — | — |" % (
                m, qm.get("dpi", ""), qm.get("planes", ""), qm.get("ink", ""),
                qm.get("colorCorrection"), s.get("result", 0), s.get("error", "")))
    out.append("")

# linearization sample
entry = d["modes"]["a3dtf1390"]["5"]
full = entry["queries"]["full_object"]["response"]
tbl = full.get("header", {}).get("remapTbl", [])
if tbl:
    out.append("#### A3 m5 的线性化曲线 `remapTbl`（每通道 256 个 double，0..1）抽样\n")
    out.append("| 通道(实测墨序 K,C,M,Y,W1,W2) | 0% | 10% | 25% | 50% | 75% | 90% | 100% |")
    out.append("|---|---|---|---|---|---|---|---|")
    for ci, ch in enumerate(tbl):
        out.append("| ch%d | %s | %s | %s | %s | %s | %s | %s |" % (
            ci, round(ch[0], 4), round(ch[25], 4), round(ch[64], 4),
            round(ch[128], 4), round(ch[192], 4), round(ch[230], 4),
            round(ch[255], 4)))
    out.append("")
    out.append("> 全部 mode 的完整 256×N 曲线保存在 `work/protocol/icc_mode_map.json` "
               "对应 `modes.<prs>.<modeId>.queries.full_object.response.header.remapTbl`；"
               "另有 `channelMax/sepLightType/kcmyGamma/dotGain/pure` 字段。\n")

# ICC files
out.append("#### ICC 文件实际位置（mtripNet CWD = …\\mtripSDK\\dist\\bin）\n")
out.append("| 相对 dist/bin 的路径 | 大小 | sha256 前 12 位 | 用途 |")
out.append("|---|---|---|---|")
usage = {
    "OUTPUT/v1440x720-A3-DTF-1390.icm": "A3 mode5 destCmyk",
    "OUTPUT/v1440x1400-A3-DTF-1390.icm": "A3 mode7 destCmyk",
    "OUTPUT/v2880x1400-A3-DTF-1390.icm": "A3 mode9 destCmyk",
    "OUTPUT/v720x720-dtf.icm": "H13 mode0 destCmyk（dist 与 bin 两份内容不同！）",
    "OUTPUT/v720x1080-dtf.icm": "H13 mode1 destCmyk",
    "OUTPUT/v720x1440-dtf.icm": "H13 mode2 destCmyk",
    "OUTPUT/v720x2160-dtf.icm": "H13 mode3 destCmyk",
    "CMYK/CoatedFOGRA39.icc": "A3 srcCmyk",
    "CMYK/US Web Coated (SWOP) v2.icc": "H13 srcCmyk",
    "RGB/SRGB IEC61966-2.1.icc": "srcRgb（两机型共用）",
    "DEFAULT/Default_cmyk.icc": "默认 CMYK 参照",
    "DEFAULT/Default_rgb.icc": "默认 RGB 参照",
    "DEFAULT/Default_gray.icc": "默认灰度参照",
}
for f in d["icc_files"]["dist"]:
    rel = f["rel"]
    if rel in usage or rel.startswith("OUTPUT/") or rel.startswith("CMYK/") or rel.startswith("RGB/"):
        out.append("| `ICC Profile/%s` | %s | %s | %s |" % (
            rel, f["size"], f["sha256"][:12], usage.get(rel, "")))
out.append("")
out.append("> `bin\\bin\\ICC Profile\\` 下有同一套文件名；除 `v720x720-dtf.icm`"
           "（dist sha256 990b5d352491…，bin 1583f84e8c…）外，其余同名 icm 的 sha256 相同。\n")

path = os.path.join(HERE, "icc_table.md")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out))
print("wrote", path, len("\n".join(out)), "chars")
