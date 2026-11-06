#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T6-A: build modeId -> ICC mapping table for A3-DTF-1390.prs and H13 XP600.prs.

For every modeId we POST three colorCorrection queries:
 1. old style   "query": ["iccPath"]
 2. old style   "query": ["channelMax","sepLightType","kcmyGamma","dotGain","remapTbl","pure"]
 3. new object  "query": {"header":{...all...}, "mcm":{pure,srcCmykPath,srcRgbPath,destCmykPath}}

Result: work/protocol/icc_mode_map.json
Also enumerates dist/bin/ICC Profile and bin/bin/ICC Profile files with sizes and
sha256 so we can state where each returned ICC name actually lives.

Sequential POST only.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

ICCP = "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/../../3rdLib/mtripSDK/dist/bin/ICC Profile"
DIST = "D:/Code/kkf/v1.1.2/rip-studio/3rdLib/mtripSDK/dist/bin"
BIN = "D:/Code/kkf/v1.1.2/rip-studio/bin/bin"
PRS = {
    "a3dtf1390": "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/A3-DTF-1390.prs",
    "h13xp600": "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/H13 XP600.prs",
}
MODES = {"a3dtf1390": list(range(0, 30)), "h13xp600": list(range(0, 4))}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def scan_icc(root):
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            out.append({"rel": rel, "abs": p.replace("\\", "/"),
                        "size": os.path.getsize(p),
                        "sha256": sha256(p)})
    return sorted(out, key=lambda x: x["rel"])


def q(prs, mode, query, tag):
    job = {"command": "colorCorrection", "prs": prs, "modeId": mode,
           "query": query}
    try:
        r = O.post(job, timeout=120)
    except Exception as e:
        r = {"_exception": repr(e)}
    return {"tag": tag, "request": job, "response": r}


def main():
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    result = {"prs": PRS,
              "icc_files": {
                  "dist": scan_icc(DIST + "/ICC Profile"),
                  "bin": scan_icc(BIN + "/ICC Profile"),
              },
              "modes": {}}
    # queryMode per prs (fresh, for dpi/planes/colorCorrection)
    qm = {}
    for key, prs in PRS.items():
        qm[key] = O.query_mode(prs)
    result["queryMode"] = {k: v for k, v in qm.items()}

    for key, prs in PRS.items():
        mode_info = {m["id"]: m for m in qm[key].get("modes", [])}
        result["modes"][key] = {}
        for mode in MODES[key]:
            entry = {"queryMode": mode_info.get(mode), "queries": {}}
            full = {"header": {"channelMax": True, "sepLightType": True,
                               "kcmyGamma": True, "dotGain": True,
                               "remapTbl": True},
                    "mcm": {"pure": True, "srcCmykPath": True,
                            "srcRgbPath": True, "destCmykPath": True}}
            for tag, query in (
                ("iccPath_old", ["iccPath"]),
                ("header_old", ["channelMax", "sepLightType", "kcmyGamma",
                                "dotGain", "remapTbl", "pure"]),
                ("full_object", full),
            ):
                r = q(prs, mode, query, tag)
                entry["queries"][tag] = r
                resp = r["response"]
                print("%-10s m%-3d %-12s result=%s %s" % (
                    key, mode, tag, resp.get("result"),
                    (resp.get("error") or "")[:26]))
            # flatten convenient summary
            resp = entry["queries"]["full_object"]["response"]
            summ = {"result": resp.get("result")}
            if resp.get("result") == 0:
                if "mcm" in resp:
                    summ["mcm"] = resp["mcm"]
                if "header" in resp:
                    h = dict(resp["header"])
                    # remapTbl is 256 doubles per channel: keep full in raw,
                    # add compact summary
                    if "remapTbl" in h and h["remapTbl"]:
                        tbl = h["remapTbl"]
                        h["remapTbl_summary"] = {
                            "channels": len(tbl),
                            "len": [len(x) for x in tbl],
                            "first5": [x[:5] for x in tbl[:8]],
                            "last5": [x[-5:] for x in tbl[:8]],
                        }
                        del h["remapTbl"]
                    summ["header"] = h
            else:
                summ["error"] = resp.get("error")
            # fall back to old-style iccPath when object query failed
            old = entry["queries"]["iccPath_old"]["response"]
            if old.get("result") == 0:
                summ["iccPath_old"] = old
            else:
                summ["iccPath_old_error"] = old.get("error") or old.get("result")
            entry["summary"] = summ
            result["modes"][key][mode] = entry
    out = os.path.join(HERE, "icc_mode_map.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("saved", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
