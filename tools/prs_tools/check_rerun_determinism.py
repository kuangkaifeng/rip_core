#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent check of T1's determinism reruns against my oracle audit.

For each (ink, tone, content pixel) in work/prs/oracle_screen_audit.json violations,
read the raw 2-bit dot from:
  - original probe: reference/prn_samples/probe_scan_<INK><tone>_176_a3dtf1390_m2.prn
  - reruns:         reference/prn_samples/rerun/probe_scan_<INK><tone>_176_a3dtf1390_m2_r{1,2}.prn
and verify all three agree (deterministic) and equal the audited anomalous level (0).
"""
import os, sys, json, importlib.util, collections
ROOT = r"D:\work\RIP核心分析"
SAMPLES = os.path.join(ROOT, 'reference', 'prn_samples')
RERUN = os.path.join(SAMPLES, 'rerun')
AUDIT = os.path.join(ROOT, 'work', 'prs', 'oracle_screen_audit.json')
PARSE = os.path.join(ROOT, 'tools', 'prn_tools', 'parse_prn.py')
UNPACK = [((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3) for b in range(256)]
COLOR = {'C': 0x00, 'M': 0x12, 'Y': 0x11, 'K': 0x04}
TOP = {'C': 640, 'M': 644, 'Y': 644, 'K': 640}

def load_parser():
    spec = importlib.util.spec_from_file_location("parse_prn", PARSE)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def dots_at(P, fn, color, targets):
    """targets: dict page_row -> list of (key, x); returns {key: dot value}."""
    d = open(fn, 'rb').read()
    job = P.parse_job(d, decode=True)
    pos = 0; out = {}
    for blk in job.blocks:
        if blk.advance is not None: pos += blk.advance
        for rec in blk.records:
            if rec.color != color or not rec.raw: continue
            for r in range(rec.m):
                pr = pos + 8*r
                tg = targets.get(pr)
                if not tg: continue
                chunk = rec.raw[r*rec.n:(r+1)*rec.n]
                for key, x in tg:
                    bi = x >> 2
                    if bi < len(chunk):
                        v = (chunk[bi] >> (6 - 2*(x & 3))) & 3
                        if v: out[key] = max(out.get(key, 0), v)
    return out

def main():
    P = load_parser()
    audit = json.load(open(AUDIT, encoding='utf-8'))
    # build tasks: (ink, tone) -> list of (key, toplevel)
    tasks = collections.defaultdict(dict)
    cells = 0
    for ink, pts in audit.items():
        for key, viol in pts.items():
            y, x = map(int, key.split(','))
            for (tone, lv, mx) in viol:
                tasks[(ink, tone)][key] = (TOP[ink] + y, x)
                cells += 1
    print(f'audit cells: {cells}, (ink,tone) jobs: {len(tasks)}')
    agree = det = total = 0
    missing = []
    for (ink, tone), targets in sorted(tasks.items()):
        # group by page row for efficiency
        by_row = collections.defaultdict(list)
        for key, (pr, x) in targets.items():
            by_row[pr].append((key, x))
        fn = os.path.join(SAMPLES, f'probe_scan_{ink}{tone:03d}_176_a3dtf1390_m2.prn')
        f1 = os.path.join(RERUN, f'probe_scan_{ink}{tone:03d}_176_a3dtf1390_m2_r1.prn')
        f2 = os.path.join(RERUN, f'probe_scan_{ink}{tone:03d}_176_a3dtf1390_m2_r2.prn')
        if not (os.path.exists(fn) and os.path.exists(f1) and os.path.exists(f2)):
            missing.append((ink, tone)); continue
        v0 = dots_at(P, fn, COLOR[ink], by_row)
        v1 = dots_at(P, f1, COLOR[ink], by_row)
        v2 = dots_at(P, f2, COLOR[ink], by_row)
        for key in targets:
            total += 1
            a, b, c = v0.get(key, 0), v1.get(key, 0), v2.get(key, 0)
            if a == b == c: det += 1
            if a == 0: agree += 1
    print(f'missing rerun jobs: {missing}')
    print(f'deterministic (orig==r1==r2): {det}/{total}')
    print(f'oracle dot == 0 (matches audit anomaly): {agree}/{total}')

if __name__ == '__main__':
    main()
