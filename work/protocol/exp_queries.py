#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Answer query requests from prs-analyst: raw queryMode / colorCorrection
responses saved as evidence under reference/jobs/queries/.

All requests are sequential. Raw response text is saved verbatim + a parsed
JSON pretty copy.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

OUT = os.path.join(WS, "reference", "jobs", "queries")
os.makedirs(OUT, exist_ok=True)

PRS_A3 = "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/A3-DTF-1390.prs"
PRS_H13 = "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/H13 XP600.prs"
PRS_H13_MYICC = "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/H13 XP600_myicc.prs"


def save(stem, job):
    raw = O._post_bytes(json.dumps(job, ensure_ascii=False).encode("utf-8"))
    text, enc = O.decode_response(raw)
    with open(os.path.join(OUT, stem + ".json"), "wb") as f:
        f.write(raw)
    try:
        resp = json.loads(text)
    except Exception:
        resp = {"_raw": text}
    print("%-42s result=%s" % (stem, resp.get("result")))
    return resp


def main():
    res = {}
    res["queryMode_A3_abs"] = save("queryMode_A3_abs",
                                   {"command": "queryMode", "prs": PRS_A3})
    res["queryMode_H13_abs"] = save("queryMode_H13_abs",
                                    {"command": "queryMode", "prs": PRS_H13})
    res["queryMode_H13_myicc_abs"] = save(
        "queryMode_H13_myicc_abs", {"command": "queryMode", "prs": PRS_H13_MYICC})
    # colorCorrection icc query for every mode id we know
    for name, prs, modes in (("A3", PRS_A3, range(0, 10)),
                             ("H13", PRS_H13, range(0, 4)),
                             ("H13myicc", PRS_H13_MYICC, range(0, 4))):
        for m in modes:
            job = {"command": "colorCorrection", "prs": prs, "modeId": m,
                   "query": {"mcm": {"srcRgbPath": True, "srcCmykPath": True,
                                     "destCmykPath": True}}}
            res["icc_%s_m%d" % (name, m)] = save("icc_%s_m%d" % (name, m), job)
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("saved to", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
