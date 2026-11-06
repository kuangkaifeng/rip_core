#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mtrip_oracle.py - drive the running MainTop mtripNet HTTP service as a RIP oracle.

The service is expected at http://127.0.0.1:8089 (mtripNet.exe, see its
mtripNet.json).  Endpoints used (doc: maint-rip-module-v2.html 4.1.1):
    POST /mtrip/v1/jobs      body = MainTopRip JSON, response = result JSON
    POST /mtrip/v1/cancel    body = {"command":"job","type":"cancel","ids":[...]}
    GET  /mtrip/v1/version
    GET  /mtrip/v1/status
    GET  /mtrip/v1/jobs/progress   SSE stream of job progress

mtripNet.exe runs with its working directory = .../mtripSDK/dist/bin, so a
relative prs name like "./A3-DTF-1390.prs" resolves there.  For printers whose
.prs only exists in rip-studio/bin/bin pass an absolute path.
ALL REQUESTED OUTPUT PATHS ARE WRITTEN BELOW THE WORKSPACE reference/ TREE.

Examples
    python mtrip_oracle.py version
    python mtrip_oracle.py status
    python mtrip_oracle.py query-mode --prs ./A3-DTF-1390.prs
    python mtrip_oracle.py rip --case probe --machine a3dtf1390 --mode 0 \
        --image reference/inputs/flat_black_64.png
    python mtrip_oracle.py post --json path/to/job.json
    python mtrip_oracle.py sse --seconds 20
    python mtrip_oracle.py prn-info --file reference/prn_samples/....prn
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

HOST = "http://127.0.0.1:8089"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))          # workspace root
INPUTS = os.path.join(WS, "reference", "inputs")
PRNS = os.path.join(WS, "reference", "prn_samples")
JOBS = os.path.join(WS, "reference", "jobs")

# prs identifiers as seen by mtripNet (relative to its CWD=dist/bin) or absolute
PRS = {
    "a3dtf1390": "./A3-DTF-1390.prs",
    "a3dtf1390_dist": "./A3-DTF-1390.prs",
    "h13xp600": "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/H13 XP600.prs",
    "h13xp600_myicc": "D:/Code/kkf/v1.1.2/rip-studio/bin/bin/H13 XP600_myicc.prs",
}

DEFAULT_TIMEOUT = 300.0

# base rip JSON template (fields per SDK doc 2.3 / observed rip-studio jobs)
BASE_JOB = {
    "command": "rip",
    "doc": {"name": ""},
    "prs": "./A3-DTF-1390.prs",
    "modeId": 0,
    "range": [[1, 1]],
    "output": {"mode": "file", "file": {"name": "", "mode": 438}},
    "rotate": 0,
    "scale": [100, 100],
    "margin": [0, 0, 0, 0],
    "view": {"xdpi": 120, "ydpi": 120},
    "color": {"readTransparency": True, "transparencyToWhite": False},
}

# golden reproducibility template: rip-studio's GemodifiseerdeMasjienRip.json /
# KaartrekenaarRip.json add a full-surface W1 channel + invaginate 10/10/10/10
WHITE_TEMPLATE = [
    {"mode": "full", "invert": False, "inkName": "W1"},
]
INKIE_TEMPLATE = [
    {"mode": "invaginate", "index": 4, "dots": [10, 10, 10, 10]},
]


def _post_bytes(body: bytes, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    req = urllib.request.Request(
        HOST + "/mtrip/v1/jobs",
        data=body,
        headers={"Content-Type": "application/json;charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def decode_response(raw: bytes):
    """mtrip reply is normally UTF-8 JSON, but errorString text can be emitted
    in the local ANSI code page (GBK on this machine); fall back gracefully."""
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace"), "utf-8/replace"


def post(obj, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """POST one MainTopRip JSON object, return parsed response dict."""
    body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    t0 = time.time()
    raw = _post_bytes(body, timeout=timeout)
    dt = time.time() - t0
    text, enc = decode_response(raw)
    try:
        resp = json.loads(text)
    except json.JSONDecodeError:
        resp = {"_raw": text}
    resp["_elapsed_s"] = round(dt, 3)
    if enc != "utf-8":
        resp["_resp_encoding"] = enc
    return resp


def get(path: str, timeout: float = 30.0) -> dict:
    with urllib.request.urlopen(HOST + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def version():
    return get("/mtrip/v1/version")


def status():
    return get("/mtrip/v1/status")


def query_mode(prs: str, inks: bool = False, timeout=DEFAULT_TIMEOUT) -> dict:
    obj = {"command": "queryMode", "prs": prs}
    if inks:
        obj["inks"] = True
    return post(obj, timeout)


def query(obj_type: str, **kw) -> dict:
    obj = {"command": "query", "type": obj_type}
    obj.update(kw)
    return post(obj)


def config(cfg_type: str, **kw) -> dict:
    obj = {"command": "config", "type": cfg_type}
    obj.update(kw)
    return post(obj)


def build_job(image, prs, mode, out, rotate=0, scale=(100, 100),
              margin=(0, 0, 0, 0), mirror=None, white="none",
              ice=None, inkie=None, dpi=(120, 120), job_id=None,
              extra=None, color=None):
    """Build a rip JSON. image/prs/out may be absolute or workspace relative."""
    job = json.loads(json.dumps(BASE_JOB))      # deep copy
    job["doc"]["name"] = _path(image, WS)
    job["prs"] = prs
    job["modeId"] = mode
    job["output"]["file"]["name"] = _path(out, PRNS)
    job["rotate"] = rotate
    job["scale"] = list(scale)
    job["margin"] = list(margin)
    job["view"] = {"xdpi": dpi[0], "ydpi": dpi[1]}
    if color:
        job["color"] = color
    if mirror:
        job["mirror"] = list(mirror)
    if white == "golden":
        job["inputColorEditor"] = json.loads(json.dumps(WHITE_TEMPLATE))
        job["inkIE"] = json.loads(json.dumps(INKIE_TEMPLATE))
    elif white == "w1w2":
        job["inputColorEditor"] = [
            {"mode": "full", "invert": False, "inkName": "W1"},
            {"mode": "full", "invert": False, "inkName": "W2"},
        ]
    elif white == "color":
        job["inputColorEditor"] = [{"mode": "color", "invert": False, "inkName": "W1"}]
    elif white == "smooth":
        job["inputColorEditor"] = [{"mode": "smooth", "invert": False, "inkName": "W1"}]
    if ice is not None:
        job["inputColorEditor"] = ice
    if inkie is not None:
        job["inkIE"] = inkie
    if job_id is not None:
        job["id"] = job_id
    if extra:
        job.update(extra)
    return job


def _path(p, base):
    p = str(p).replace("\\", "/")
    if os.path.isabs(p):
        return p
    if base:
        return os.path.abspath(os.path.join(base, p)).replace("\\", "/")
    return p


def run_job(job, tag, save=True, timeout=DEFAULT_TIMEOUT):
    """POST one job, persist job JSON + response + prn bytes metadata.

    Returns dict with keys: tag, job, job_path, response, prn, prn_size, ok.
    """
    os.makedirs(JOBS, exist_ok=True)
    os.makedirs(PRNS, exist_ok=True)
    job_path = os.path.join(JOBS, tag + ".json")
    resp_path = os.path.join(JOBS, tag + ".resp.json")
    if save:
        with open(job_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(job, f, ensure_ascii=False, indent=2)
    resp = post(job, timeout=timeout)
    if save:
        with open(resp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(resp, f, ensure_ascii=False, indent=2)
    prn = str(job.get("output", {}).get("file", {}).get("name", ""))
    size = os.path.getsize(prn) if prn and os.path.isfile(prn) else 0
    return {"tag": tag, "job": job, "job_path": job_path, "response": resp,
            "prn": prn, "prn_size": size, "ok": resp.get("result") == 0}


def prn_info(path, head=64):
    import binascii
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        b = f.read(head)
    printable = "".join(chr(c) if 32 <= c < 127 else "." for c in b)
    return {"file": path, "size": size,
            "head_hex": binascii.hexlify(b).decode(),
            "head_ascii": printable,
            "magic_esc_p2_ejl": b[:6].hex().lower() == "1b0140454a4c",
            "magic_hssf_0x5555": b[:2] == b"\x55\x55",
            "magic_ycdz": b[:4] == bytes.fromhex("7a646379")}


# --- PRN hashing / comparison utilities -----------------------------------
# ESC/P2 (A3-DTF-1390) jobs embed a creation timestamp in the remote-mode TI
# tag: the TI payload is 8 bytes at file offset 44..51 = 00 + year(BE16) month
# day hour minute second.  It is the ONLY non-deterministic content of the
# generated PRN (verified by byte-diffing repeated runs); normalize it before
# comparing vendor/oracle files.  Remote-tag layout observed at offset 28:
#   ESC ( R 08 00 00 'REMOTE1' | 'TI' 08 00 00 00 07 EA 0B 06 0E 20 19 | 'JS' ...
TI_TAG_OFFSET = 40      # 'TI' tag id
TI_OFFSET = 45          # first timestamp byte (year high byte)
TI_LEN = 7


def normalize_prn_bytes(data: bytes) -> bytes:
    b = bytearray(data)
    if b[:5] == bytes.fromhex("0000001b01") and b[TI_TAG_OFFSET:TI_TAG_OFFSET + 2] == b"TI":
        b[TI_OFFSET:TI_OFFSET + TI_LEN] = b"\x00" * TI_LEN
    return bytes(b)


def sha256_file(path, normalize=False):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        if normalize:
            h.update(normalize_prn_bytes(f.read()))
        else:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


def diff_prn(path_a, path_b, max_ranges=20):
    a = open(path_a, "rb").read()
    b = open(path_b, "rb").read()
    an, bn = normalize_prn_bytes(a), normalize_prn_bytes(b)
    def _ranges(x, y):
        n = min(len(x), len(y))
        out, i = [], 0
        while i < n:
            if x[i] != y[i]:
                j = i
                while j < n and x[j] != y[j]:
                    j += 1
                out.append((i, j))
                i = j
            else:
                i += 1
        return out
    raw_d, norm_d = _ranges(a, b), _ranges(an, bn)
    return {"a": path_a, "b": path_b, "len_a": len(a), "len_b": len(b),
            "raw_diff_ranges": raw_d[:max_ranges], "raw_diff_count": len(raw_d),
            "norm_diff_ranges": norm_d[:max_ranges], "norm_diff_count": len(norm_d),
            "identical_normalized": norm_d == [] and len(a) == len(b)}



# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="MainTop mtripNet HTTP oracle")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version")
    sub.add_parser("status")

    p = sub.add_parser("query-mode")
    p.add_argument("--prs", default=PRS["a3dtf1390"])
    p.add_argument("--inks", action="store_true")

    p = sub.add_parser("post")
    p.add_argument("--json", required=True)

    p = sub.add_parser("rip")
    p.add_argument("--case", required=True, help="output stem, e.g. probe_black_64_m0")
    p.add_argument("--machine", default="a3dtf1390", choices=list(PRS.keys()))
    p.add_argument("--prs", default=None)
    p.add_argument("--mode", type=int, default=0)
    p.add_argument("--image", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--rotate", type=float, default=0)
    p.add_argument("--scale", type=float, nargs=2, default=(100, 100))
    p.add_argument("--margin", type=float, nargs=4, default=(0, 0, 0, 0))
    p.add_argument("--mirror", type=int, nargs=2, default=None)
    p.add_argument("--white", default="none",
                   choices=["none", "golden", "w1w2", "color", "smooth"])
    p.add_argument("--ice-json", default=None, help="file containing inputColorEditor array")
    p.add_argument("--inkie-json", default=None)
    p.add_argument("--dpi", type=float, nargs=2, default=(120, 120))
    p.add_argument("--id", type=int, default=None)
    p.add_argument("--extra-json", default=None, help="file with extra top-level fields")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("sse")
    p.add_argument("--seconds", type=float, default=15.0)

    p = sub.add_parser("cancel")
    p.add_argument("ids", type=int, nargs="+")

    p = sub.add_parser("prn-info")
    p.add_argument("--file", required=True)
    p.add_argument("--head", type=int, default=64)

    p = sub.add_parser("compare")
    p.add_argument("file_a")
    p.add_argument("file_b")

    a = ap.parse_args(argv)

    if a.cmd == "version":
        print(json.dumps(version(), ensure_ascii=False, indent=2))
    elif a.cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    elif a.cmd == "query-mode":
        print(json.dumps(query_mode(a.prs, a.inks), ensure_ascii=False, indent=2))
    elif a.cmd == "post":
        with open(a.json, "r", encoding="utf-8-sig") as f:
            obj = json.load(f)
        print(json.dumps(post(obj), ensure_ascii=False, indent=2))
    elif a.cmd == "rip":
        prs = a.prs or PRS[a.machine]
        out = a.out or os.path.join(PRNS, a.case + ".prn")
        ice = inkie = extra = None
        if a.ice_json:
            with open(a.ice_json, "r", encoding="utf-8-sig") as f:
                ice = json.load(f)
        if a.inkie_json:
            with open(a.inkie_json, "r", encoding="utf-8-sig") as f:
                inkie = json.load(f)
        if a.extra_json:
            with open(a.extra_json, "r", encoding="utf-8-sig") as f:
                extra = json.load(f)
        job = build_job(a.image, prs, a.mode, out,
                        rotate=a.rotate, scale=a.scale, margin=a.margin,
                        mirror=a.mirror, white=a.white, ice=ice, inkie=inkie,
                        dpi=a.dpi, job_id=a.id, extra=extra)
        if a.dry_run:
            print(json.dumps(job, ensure_ascii=False, indent=2))
            return 0
        r = run_job(job, a.case)
        info = prn_info(r["prn"]) if r["prn_size"] else None
        print(json.dumps({"tag": r["tag"], "response": r["response"],
                          "job_path": r["job_path"], "prn": r["prn"],
                          "prn_size": r["prn_size"], "prn_info": info},
                         ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    elif a.cmd == "sse":
        url = HOST + "/mtrip/v1/jobs/progress"
        t0 = time.time()
        req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
        try:
            with urllib.request.urlopen(req, timeout=max(2, a.seconds)) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    print(f"[{time.time()-t0:7.3f}] {line}", flush=True)
                    if time.time() - t0 > a.seconds:
                        break
        except Exception as e:      # timeout/closed is normal
            print(f"[sse end] {e}", file=sys.stderr)
    elif a.cmd == "cancel":
        body = json.dumps({"command": "job", "type": "cancel", "ids": a.ids}).encode()
        print(_post_raw(body))
    elif a.cmd == "prn-info":
        info = prn_info(a.file, a.head)
        info["sha256"] = sha256_file(a.file)
        info["sha256_norm"] = sha256_file(a.file, normalize=True)
        print(json.dumps(info, ensure_ascii=False, indent=2))
    elif a.cmd == "compare":
        print(json.dumps(diff_prn(a.file_a, a.file_b), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
