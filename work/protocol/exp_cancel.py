#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cancel semantics test: POST a long-ish job, then POST /mtrip/v1/cancel.

Endpoint mapping from doc 4.1.1: /mtrip/v1/cancel implements MainTopRipCancel
(global cancel of the running operation), NOT the job-cancel JSON command.
"""
import json
import os
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

EV = os.path.join(HERE, "evidence")


def post_async(job, result_holder):
    def _run():
        t0 = time.time()
        try:
            resp = O.post(job, timeout=120)
        except Exception as e:
            resp = {"_exception": repr(e)}
        result_holder.append((resp, time.time() - t0))
    t = threading.Thread(target=_run)
    t.start()
    return t


def cancel():
    req = urllib.request.Request(O.HOST + "/mtrip/v1/cancel", data=b"",
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    return {"body": body, "elapsed_s": round(time.time() - t0, 3)}


def main():
    os.makedirs(EV, exist_ok=True)
    trials = []
    for i in (1, 2):
        tag = f"cancel_trial{i}"
        out = os.path.join(O.PRNS, tag + ".prn").replace("\\", "/")
        job = O.build_job("reference/inputs/cmyk_quad_720.png", O.PRS["a3dtf1390"],
                          6, out, job_id=1000 + i)
        # persist the job json (evidence)
        with open(os.path.join(O.JOBS, tag + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(job, f, ensure_ascii=False, indent=2)
        holder = []
        th = post_async(job, holder)
        delay = 0.5
        time.sleep(delay)
        c = cancel()
        th.join(120)
        resp, job_elapsed = holder[0] if holder else ({}, -1)
        prn = out
        trials.append({
            "tag": tag, "id": job.get("id"), "cancel_after_s": delay,
            "cancel_response": c, "job_response": resp,
            "job_elapsed_s": round(job_elapsed, 3),
            "prn_exists": os.path.isfile(prn),
            "prn_size": os.path.getsize(prn) if os.path.isfile(prn) else None,
        })
        print(json.dumps(trials[-1], ensure_ascii=False, indent=1))

    with open(os.path.join(EV, "cancel.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(trials, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
