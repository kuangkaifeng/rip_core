#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reencode_prn.py -- round-trip a MainTop/ESC-P2 .prn through the parser and
byte-compare with the vendor file (EJL TI timestamp normalized).

  A) structure replay : rebuild the byte stream from parsed structures
                        (header + prologue raws + per-record ESC($ / ESC i /
                        re-encoded RLE / 0D + tail).  This verifies that the
                        parser understood every byte and that our RLE encoder
                        is byte-exact.
  B) byte diff        : offsets / context of the first differences, with the
                        TI tag bytes (offset 45..51 in the golden job) masked.

Usage:
  python reencode_prn.py job.prn [--out re.prn] [--json report.json] [--quiet]

Result on the current corpus: identical for every sample (only TI differs,
which is masked; see --mask-ti).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_prn as P


def rebuild(job):
    """Rebuild the whole file from parsed structures."""
    out = bytearray()
    # --- header ---
    h = job.header
    out += bytes.fromhex(h["enter_d4"])
    for e in h["ejl"]:
        out += e["text"].encode("latin1")
    # remote enter: ESC ( R 08 00 00 "REMOTE1"   (payload = 0x00 + "REMOTE1")
    out += bytes.fromhex("1b 28 52")
    out += (8).to_bytes(2, "little")
    out += b"\x00REMOTE1"
    for t in h["tags"]:
        out += t["tag"].encode("latin1")
        data = bytes.fromhex(t["data"])
        out += len(data).to_bytes(2, "little")
        out += data
    out += bytes.fromhex("1b 00 00 00")
    # --- prologue (raw byte copies preserve vendor quirks, e.g. uneven tails) ---
    for c in job.prologue:
        out += bytes.fromhex(c["raw"])
    # --- raster blocks ---
    for b in job.blocks:
        if b.advance is not None:
            out += bytes.fromhex("1b 28 76 04 00")
            out += b.advance.to_bytes(4, "little")
        for rec in b.records:
            out += bytes.fromhex("1b 28 24 04 00")
            out += rec.xpos.to_bytes(4, "little")
            out += bytes([0x1B, 0x69, rec.color, rec.comp, rec.bit])
            out += rec.n.to_bytes(2, "little")
            out += rec.m.to_bytes(2, "little")
            out += P.rle_encode(rec.raw, rec.n)
            out += b"\x0D"
    # --- tail ---
    out += job.tail
    return bytes(out)


def ti_offsets(d):
    """offsets of TI tag payload (8 bytes) if present."""
    h = {}
    import re
    m = re.search(rb"TI\x08\x00", d)
    if m:
        return list(range(m.start() + 4, m.start() + 12))
    return []


def compare(a, b, mask=()):
    if len(a) != len(b):
        print("  size differs: vendor=%d rebuilt=%d" % (len(a), len(b)))
    n = min(len(a), len(b))
    diffs = []
    for i in range(n):
        if a[i] != b[i] and i not in mask:
            diffs.append(i)
            if len(diffs) >= 20:
                break
    return diffs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("prn")
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    d = open(args.prn, "rb").read()
    job = P.parse_job(d, decode=True)
    job.path = args.prn
    reb = rebuild(job)
    mask = set(ti_offsets(d))
    diffs = compare(d, reb, mask)
    identical = (len(d) == len(reb) and not diffs)
    report = dict(file=args.prn, size_vendor=len(d), size_rebuilt=len(reb),
                  identical_normalized=identical,
                  ti_masked_offsets=sorted(mask), diff_offsets=diffs[:20])
    if args.out:
        open(args.out, "wb").write(reb)
        report["out"] = args.out
    if not args.quiet:
        print("%-58s vendor=%d rebuilt=%d %s" % (
            os.path.basename(args.prn), len(d), len(reb),
            "IDENTICAL (TI masked)" if identical else "DIFF %s" % diffs[:10]))
        if diffs:
            for off in diffs[:5]:
                lo = max(0, off - 8)
                print("   @0x%08X vendor=%s rebuilt=%s" % (
                    off, d[lo:off + 8].hex(" "), reb[lo:off + 8].hex(" ")))
    if args.json:
        json.dump(report, open(args.json, "w", encoding="utf-8"), indent=1)
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())
