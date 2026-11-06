#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FINAL isolated retest of the fatal `dpi` (customDpi) field.

Single POST only; if mtripNet dies, record evidence and stop (no repeat).
"""
import json
import os
import sys
import time
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

EV = os.path.join(HERE, "evidence")


def health():
    try:
        return O.get("/mtrip/v1/status").get("result") == 0
    except Exception:
        return False


def main():
    rec = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
           "health_before": health()}
    out = os.path.join(O.PRNS, "exp_a3dtf1390_dpi_300_retest.prn").replace("\\", "/")
    job = O.build_job("reference/inputs/flat_black_100.png", "./A3-DTF-1390.prs",
                      2, out, extra={"dpi": {"xdpi": 300, "ydpi": 300}})
    job_path = os.path.join(O.JOBS, "exp_a3dtf1390_dpi_300_retest.json")
    with open(job_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    rec["job"] = job
    rec["job_json"] = job_path
    try:
        t0 = time.time()
        resp = O.post(job, timeout=60)
        rec["response"] = resp
        rec["elapsed_s"] = round(time.time() - t0, 3)
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        rec["exception"] = repr(e)
        rec["elapsed_s"] = round(time.time() - t0, 3)
    time.sleep(2.0)
    rec["health_after"] = health()
    rec["prn_exists"] = os.path.isfile(out)
    rec["prn_size"] = os.path.getsize(out) if os.path.isfile(out) else None
    rec["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(EV, "dpi_crash_retest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    print(json.dumps(rec, ensure_ascii=False, indent=1)[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
