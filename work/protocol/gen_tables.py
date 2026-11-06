#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate markdown tables for docs/maintop_api.md from the evidence JSONs."""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

EV = os.path.join(HERE, "evidence")
OUT = os.path.join(EV, "tables.md")


def load(name):
    try:
        return json.load(open(os.path.join(EV, name), encoding="utf-8"))
    except Exception:
        return None


def corpus_table():
    """case x modeId -> size for base variants (proves modeId effect)."""
    rows = {}
    for prn in glob.glob(os.path.join(O.PRNS, "*_m[0-3].prn")):
        stem = os.path.basename(prn)[:-4]
        parts = stem.rsplit("_m", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            continue
        base, mode = parts
        machine = "h13xp600" if base.startswith("h13xp600") else "a3dtf1390"
        case = base[len(machine) + 1:]
        if "golden" in case or "w1w2" in case or case.startswith("exp_") or case.startswith("geom"):
            continue
        if case.startswith("probe") or case.startswith("det") or case.startswith("sse") or case.startswith("cache"):
            continue
        rows.setdefault(case, {})[(machine, int(mode))] = os.path.getsize(prn)
    lines = ["| case (100x100, base template) | A3 m0 | A3 m1 | A3 m2 | A3 m3 | H13 m0 | H13 m1 | H13 m2 | H13 m3 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for case in sorted(rows):
        r = rows[case]
        vals = []
        ok = True
        for machine in ("a3dtf1390", "h13xp600"):
            for mode in range(4):
                v = r.get((machine, mode))
                if v is None:
                    ok = False
                    break
                vals.append(f"{v:,}")
            if not ok:
                break
        if ok:
            lines.append("| " + case + " | " + " | ".join(vals) + " |")
    return "\n".join(lines)


def exp_table():
    feats = {}
    for name in ("exp_features.json", "exp_params2.json"):
        data = load(name) or []
        for r in data:
            f = r.get("features") or {}
            base = O.PRNS
            if r.get("prn"):
                feats[os.path.basename(r["prn"])] = (r, f)
    # baseline corpus numbers
    base_feat = {}
    for k in ("a3dtf1390_cmyk_quad_100_m2.prn", "a3dtf1390_m3_golden.prn"):
        pass
    lines = ["| 实验 | 关键参数 | PRN 大小 B | blocks | advance | 4色覆盖率 | 结论 |",
             "|---|---|---|---|---|---|---|"]
    order = sorted(feats, key=lambda k: feats[k][0].get("name", k))
    for prn in order:
        r, f = feats[prn]
        stem = prn[:-4]
        if "colors" not in f:
            continue
        cov = {c: round(v["coverage"], 3) for c, v in f["colors"].items()}
        covstr = " ".join(f"{k}:{v}" for k, v in cov.items())
        params = r.get("params") or {}
        key = "; ".join("%s=%s" % (k, v) for k, v in params.items()
                        if k in ("rotate", "scale", "margin", "mirror", "view", "dpi",
                                 "inkIE", "inputColorEditor", "whiteInk", "color"))
        lines.append("| %s | %s | %s | %s | %s | %s |  |" % (
            stem, key[:80], f.get("size"), f.get("blocks"), f.get("advances"), covstr))
    return "\n".join(lines)


def white_table():
    wm = load("white_matrix.json") or []
    lines = ["| stem | mode | 附加通道方式 | PRN 大小 | 颜色码覆盖率 |",
             "|---|---|---|---|---|"]
    for r in wm:
        f = r.get("features") or {}
        cov = {c: round(v["coverage"], 3) for c, v in f.get("colors", {}).items()}
        how = "legacy whiteInk" if r.get("extra") else "inputColorEditor W1"
        lines.append("| %s | %s | %s | %s | %s |" % (
            r["stem"], r.get("mode"), how, f.get("size"),
            " ".join(f"{k}:{v}" for k, v in cov.items())))
    return "\n".join(lines)


def main():
    md = []
    md.append("## 附 A：基础语料 case×modeId 大小表\n\n" + corpus_table())
    md.append("\n## 附 B：参数实验特征表\n\n" + exp_table())
    md.append("\n## 附 C：白墨/透明矩阵\n\n" + white_table())
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))
    print("wrote", OUT, len("\n".join(md)), "chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
