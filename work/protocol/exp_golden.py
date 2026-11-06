#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the HTTP oracle against the known golden pair and check determinism.

Golden pair (in rip-studio bin/bin/temp):
    pic/1793946733018.png  --(GemodifiseerdeMasjienRip.json)-->  data/1793946733280.prn
modeId=2, A3-DTF-1390.prs, inputColorEditor W1 full, inkIE invaginate 10/10/10/10.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "oracle"))
import mtrip_oracle as O   # noqa: E402

SRC_IMG = "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/temp/pic/1793946733018.png"
SRC_PRN = "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/temp/data/1793946733280.prn"
GOLDEN_JOB = "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/GemodifiseerdeMasjienRip.json"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmp_hashes(tag, job, out):
    r = O.run_job(job, tag)
    print(f"\n[{tag}] result={r['response'].get('result')} elapsed={r['response'].get('_elapsed_s')}s size={r['prn_size']}")
    if os.path.isfile(out):
        print(f"  sha256={sha(out)}")
    if os.path.isfile(SRC_PRN):
        print(f"  golden sha256={sha(SRC_PRN)} size={os.path.getsize(SRC_PRN)}")
    return out


def main():
    os.makedirs(O.JOBS, exist_ok=True)
    if not os.path.isfile(SRC_IMG):
        print("golden input missing, abort"); return 2
    # 1. exact replay of the rip-studio job, output redirected into the workspace
    job = json.load(open(GOLDEN_JOB, "r", encoding="utf-8-sig"))
    out1 = os.path.join(O.PRNS, "golden_repro_1793946733280.prn").replace("\\", "/")
    job["output"]["file"]["name"] = out1
    cmp_hashes("golden_repro", job, out1)

    # 2. determinism: repeat the exact golden job a second time
    out2 = os.path.join(O.PRNS, "golden_repro_1793946733280_again.prn").replace("\\", "/")
    job2 = json.loads(json.dumps(job))
    job2["output"]["file"]["name"] = out2
    cmp_hashes("golden_repro_again", job2, out2)

    # 3. determinism on a simple synthetic job
    for i in (1, 2):
        j = O.build_job("reference/inputs/flat_black_64.png", O.PRS["a3dtf1390"], 0,
                        os.path.join(O.PRNS, f"det_{i}.prn"), )
        cmp_hashes(f"det_{i}", j, j["output"]["file"]["name"])
    # also compare to first probe (same params, different name)
    probe = os.path.join(O.PRNS, "probe_black_64_m0.prn")
    if os.path.isfile(probe):
        print(f"\nprobe_black_64_m0.prn sha256={sha(probe)} size={os.path.getsize(probe)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
