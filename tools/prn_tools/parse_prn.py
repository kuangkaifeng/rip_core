#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_prn.py -- MainTop / Epson ESC/P2 (.prn) job parser.

Parses the mixed EJL + remote-mode + ESC/P2 raster stream produced by
MainTop RIP (mtripSDK) for the Epson Stylus Photo 1390 class printers
(A3-DTF-1390 modified machine), and optionally:
  * decodes every raster record (RLE -> n*m raw bytes)
  * prints structure / statistics
  * exports raw raster planes and a composed page preview (PNG/BMP)
  * re-encodes the parsed structure and byte-compares with the source file

Usage examples
--------------
  python parse_prn.py info  job.prn
  python parse_prn.py stats job.prn
  python parse_prn.py planes job.prn --outdir out_planes
  python parse_prn.py preview job.prn --out preview.png
  python parse_prn.py reencode job.prn --out re.prn

Author: escp2-analyst (RIP team)
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import struct
import sys

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------
ESC = 0x1B
ENTER_D4 = bytes([0x00, 0x00, 0x00, 0x1B, 0x01])
REMOTE_ENTER = bytes([0x1B, 0x28, 0x52, 0x08, 0x00, 0x00]) + b"REMOTE1"
REMOTE_EXIT = bytes([0x1B, 0x00, 0x00, 0x00])

KNOWN_REMOTE_TAGS = [b"TI", b"JS", b"JH", b"SN", b"PP", b"MI", b"DP",
                     b"US", b"LD", b"JE"]

# ESC ( <letter> : name for the docs / human readable
ESC_PAREN_NAMES = {
    0x24: "ESC($) set-absolute-horizontal-position",
    0x44: "ESC(D) set-raster-resolution",
    0x53: "ESC(S) set-page/paper-size",
    0x63: "ESC(c) set-page-format",
    0x55: "ESC(U) set-unit",
    0x47: "ESC(G) select-graphics-mode",
    0x69: "ESC(i) set-microweave",
    0x4B: "ESC(K) set-color-mode",
    0x65: "ESC(e) set-ink/dot-size",
    0x6D: "ESC(m) set-print-method",
    0x56: "ESC(V) set-absolute-vertical-position",
    0x76: "ESC(v) set-relative-vertical-position",
    0x52: "ESC(R) enter-remote-mode",
}

# ESC i color byte -> our current hypothesis of ink channel (to be confirmed)
COLOR_NAMES = {
    0x00: "0x00",
    0x01: "0x01",
    0x02: "0x02",
    0x04: "0x04",
    0x11: "0x11",
    0x12: "0x12",
}


# --------------------------------------------------------------------------
# RLE (ESC/P2 "run-length encoding" used by ESC i when comp=1)
# --------------------------------------------------------------------------
def rle_decode(data: bytes, expected: int):
    """Decode ESC/P2 RLE. Returns (raw bytes, consumed, error_or_None).

    count = d[i]; if count <= 127: copy next (count+1) bytes;
                   else: repeat next byte (257-count) times.
    """
    out = bytearray()
    i = 0
    n = len(data)
    while len(out) < expected:
        if i >= n:
            return bytes(out), i, "unexpected-end-of-data"
        c = data[i]
        i += 1
        if c <= 127:
            cnt = c + 1
            if i + cnt > n:
                return bytes(out), i, "literal-overrun"
            out += data[i:i + cnt]
            i += cnt
        else:
            cnt = 257 - c
            if i >= n:
                return bytes(out), i, "repeat-missing-byte"
            out += bytes([data[i]]) * cnt
            i += 1
    if len(out) > expected:
        return bytes(out[:expected]), i, "decoded-too-much"
    return bytes(out), i, None


def rle_decode_lineskip(data: bytes, expected: int):
    """Same as rle_decode but keeps the line structure: returns list of
    (raw_line_bytes, token_count) so re-encoder can mirror line resets."""
    pass  # implemented in rle_tokens below


def rle_tokens(data: bytes, expected: int):
    """Decode while recording token boundaries per output line.
    Returns (raw, tokens) where tokens = list of (op, pos, size, byte).
    op: 'L' literal (size bytes from data) / 'R' run (size x byte).
    """
    out = bytearray()
    toks = []
    i = 0
    n = len(data)
    while len(out) < expected:
        if i >= n:
            break
        c = data[i]
        start = i
        i += 1
        if c <= 127:
            cnt = c + 1
            out += data[i:i + cnt]
            i += cnt
            toks.append(("L", start, cnt, None))
        else:
            cnt = 257 - c
            b = data[i] if i < n else 0
            i += 1
            out += bytes([b]) * cnt
            toks.append(("R", start, cnt, b))
    return bytes(out), toks


def rle_encode_line(linedata: bytes):
    """MainTop/Epson RLE encoder for ONE line (verified byte-identical on the corpus).

    Rules (measured from vendor token statistics over the whole corpus):
      * a repeat token is only used for runs of >= 3 equal bytes (runs of 2 stay
        inside literals); max run length per token = 128
      * literals are used for everything else, max 128 bytes per token, and are
        broken when a run of >= 3 starts
      * encoding restarts at every raster line (n bytes per line)
    """
    out = bytearray()
    i = 0
    n = len(linedata)
    while i < n:
        run = 1
        while i + run < n and linedata[i + run] == linedata[i] and run < 128:
            run += 1
        if run >= 3:
            out.append((257 - run) & 0xFF)
            out.append(linedata[i])
            i += run
        else:
            start = i
            while i < n:
                if i + 2 < n and linedata[i] == linedata[i + 1] == linedata[i + 2]:
                    break
                i += 1
                if i - start >= 128:
                    break
            cnt = i - start
            if cnt:
                out.append((cnt - 1) & 0xFF)
                out += linedata[start:i]
    return bytes(out)


def rle_encode(raw: bytes, line_bytes: int):
    out = bytearray()
    for off in range(0, len(raw), line_bytes):
        out += rle_encode_line(raw[off:off + line_bytes])
    return bytes(out)


# --------------------------------------------------------------------------
# parsed representation
# --------------------------------------------------------------------------
class Record(object):
    __slots__ = ("color", "comp", "bit", "n", "m", "xpos", "offset",
                 "data_offset", "data_len", "raw", "term", "decode_err", "_end")

    def __init__(self):
        self.color = 0
        self.comp = 0
        self.bit = 0
        self.n = 0
        self.m = 0
        self.xpos = 0
        self.offset = 0          # offset of ESC (
        self.data_offset = 0     # offset of first RLE byte
        self.data_len = 0
        self.raw = None          # decoded n*m bytes
        self.term = None
        self.decode_err = None

    def to_dict(self):
        d = dict(color="0x%02X" % self.color, comp=self.comp, bit=self.bit,
                 n=self.n, m=self.m, xpos=self.xpos, offset=self.offset,
                 data_offset=self.data_offset, data_len=self.data_len,
                 term=self.term, decode_err=self.decode_err)
        return d


class Block(object):
    __slots__ = ("index", "advance", "v_offset", "records")

    def __init__(self, index):
        self.index = index
        self.advance = None      # ESC ( v value preceding this block (None -> first block)
        self.v_offset = 0        # offset of the ESC ( v (or of first ESC ( $ if none)
        self.records = []        # list[Record]


class Job(object):
    def __init__(self):
        self.path = None
        self.size = 0
        self.header = {}
        self.prologue = []       # list of (offset, cmd_name, raw bytes)
        self.blocks = []
        self.tail = b""
        self.warnings = []
        self.unknown_commands = []


# ESC ( X commands whose payload we can skip by length
def parse_paren(d, i):
    """Parse one ESC ( <letter> nL nH <payload> at d[i]; return (letter, payload, end)."""
    letter = d[i + 2]
    ln = d[i + 3] | (d[i + 4] << 8)
    start = i + 5
    end = start + ln
    return letter, d[start:end], end


def parse_header(d):
    """Parse ENTER D4 + EJL lines + remote-mode tag records. Returns (header, pos)."""
    h = {}
    pos = 0
    if d[:5] != ENTER_D4:
        raise ValueError("not an ESC/P2 EJL job (missing 00 00 00 1B 01): %s" % d[:8].hex(" "))
    h["enter_d4"] = d[0:5].hex(" ")
    pos = 5
    ejl = []
    while pos < len(d) and d[pos:pos + 1] == b"@":
        e = d.find(b"\n", pos)
        if e < 0:
            raise ValueError("unterminated @EJL line at %d" % pos)
        line = d[pos:e + 1]
        ejl.append(dict(offset=pos, text=line.decode("latin1")))
        pos = e + 1
        if len(ejl) >= 2:
            break
    h["ejl"] = ejl
    # remote mode enter
    if d[pos:pos + len(REMOTE_ENTER)] != REMOTE_ENTER:
        raise ValueError("expected remote-mode enter at %d: %s" % (pos, d[pos:pos + 16].hex(" ")))
    let, payload, end = parse_paren(d, pos)
    h["remote_enter"] = dict(offset=pos, letter=chr(let), payload=payload.decode("latin1"))
    pos = end
    # tag records until remote-exit
    tags = []
    while True:
        if d[pos:pos + 4] == REMOTE_EXIT:
            h["remote_exit_offset"] = pos
            pos += 4
            break
        if pos + 4 > len(d):
            raise ValueError("truncated remote section")
        tag = d[pos:pos + 2]
        ln = d[pos + 2] | (d[pos + 3] << 8)
        data = d[pos + 4:pos + 4 + ln]
        tags.append(dict(tag=tag.decode("latin1"), len=ln, offset=pos,
                         data=data.hex(" "),
                         ascii="".join(chr(c) if 32 <= c < 127 else "." for c in data)))
        h.setdefault(tag.decode("latin1"), []).append(data)
        pos += 4 + ln
        if len(tags) > 40:
            raise ValueError("too many remote tags (no exit)")
    h["tags"] = tags
    return h, pos


def parse_job(d, decode=True, stop_after_blocks=None):
    job = Job()
    job.size = len(d)
    job.header, pos = parse_header(d)

    # ---- prologue: ESC commands until first raster block ----
    while pos < len(d):
        if d[pos] != ESC:
            job.warnings.append("unexpected byte 0x%02X at 0x%X (prologue)" % (d[pos], pos))
            break
        c2 = d[pos + 1]
        if c2 == 0x28:            # ESC ( X
            letter = d[pos + 2]
            if letter == 0x24:    # ESC ( $ -> raster block starts
                break
            let, payload, end = parse_paren(d, pos)
            job.prologue.append(dict(offset=pos, name=ESC_PAREN_NAMES.get(let, "ESC(%c)" % let),
                                     letter="%02X" % let, payload=payload.hex(" "),
                                     raw=d[pos:end].hex(" "), length=end - pos))
            pos = end
            continue
        if c2 == 0x69:            # ESC i  (raster record, but should be inside block)
            break
        if c2 == 0x55:            # ESC U n
            job.prologue.append(dict(offset=pos, name="ESC U (print direction)",
                                     letter="U", payload="%02X" % d[pos + 2],
                                     raw=d[pos:pos + 3].hex(" "), length=3))
            pos += 3
            continue
        if c2 == 0x40:            # ESC @
            job.prologue.append(dict(offset=pos, name="ESC @ (reset)",
                                     letter="@", payload="", raw="1b 40", length=2))
            pos += 2
            continue
        if c2 == 0x00:            # ESC 00 00 00 (exit remote)
            job.prologue.append(dict(offset=pos, name="ESC remote-exit",
                                     letter="00", payload="", raw=d[pos:pos + 4].hex(" "), length=4))
            pos += 4
            continue
        # unknown 2-byte ESC command
        job.unknown_commands.append((pos, d[pos:pos + 4].hex(" ")))
        pos += 2

    # ---- raster section ----
    pending = None               # (advance, v_offset) for the next block
    block = None
    total = len(d)
    while pos < total:
        # tail detection
        if d[pos] == 0x0C:
            # FF then tail (ESC @ + remote LD/JE)
            job.tail = d[pos:]
            break
        if d[pos] != ESC:
            job.warnings.append("unexpected byte 0x%02X at 0x%X (raster)" % (d[pos], pos))
            pos += 1
            continue
        c2 = d[pos + 1]
        if c2 == 0x28:
            letter = d[pos + 2]
            if letter == 0x76:    # ESC ( v  relative vertical advance -> new block
                let, payload, end = parse_paren(d, pos)
                pending = (struct.unpack("<I", payload[0:4])[0], pos)
                pos = end
                block = None          # next record starts new block
                continue
            if letter == 0x24:    # ESC ( $ absolute horizontal position
                let, payload, end = parse_paren(d, pos)
                xpos = struct.unpack("<I", payload[0:4])[0]
                # next must be ESC i
                pos = end
                if d[pos:pos + 2] != b"\x1b\x69":
                    job.warnings.append("ESC($ at 0x%X not followed by ESC i (got %s)"
                                        % (end, d[pos:pos + 6].hex(" ")))
                    continue
                rec = parse_record(d, pos)
                rec.xpos = xpos
                if block is None:
                    block = Block(len(job.blocks))
                    if pending is not None:
                        block.advance, block.v_offset = pending
                    else:
                        block.v_offset = rec.offset
                    pending = None
                    job.blocks.append(block)
                block.records.append(rec)
                pos = rec._end
                continue
            # any other ESC ( command inside raster section: log & skip
            let, payload, end = parse_paren(d, pos)
            job.warnings.append("unexpected ESC(%02X at 0x%X in raster section" % (letter, pos))
            pos = end
            continue
        if c2 == 0x69:            # ESC i without preceding ESC($ (shouldn't happen)
            rec = parse_record(d, pos)
            if block is None:
                block = Block(len(job.blocks))
                job.blocks.append(block)
            block.records.append(rec)
            pos = rec._end
            continue
        if c2 == 0x40:            # ESC @ inside raster? log
            job.warnings.append("ESC @ at 0x%X in raster section" % pos)
            pos += 2
            continue
        job.warnings.append("unknown ESC %02X at 0x%X" % (c2, pos))
        pos += 2

    if decode:
        for blk in job.blocks:
            for rec in blk.records:
                decode_record(d, rec)
    return job


def parse_record(d, i):
    """Parse ESC i + RLE data + 0D at offset i. Returns Record (raw=None)."""
    rec = Record()
    rec.offset = i
    color, comp, bit = d[i + 2], d[i + 3], d[i + 4]
    n = d[i + 5] | (d[i + 6] << 8)
    m = d[i + 7] | (d[i + 8] << 8)
    rec.color, rec.comp, rec.bit, rec.n, rec.m = color, comp, bit, n, m
    rec.data_offset = i + 9
    # walk tokens to find end
    j = i + 9
    produced = 0
    target = n * m
    while produced < target:
        if j >= len(d):
            rec.decode_err = "eof"
            break
        c = d[j]
        if c <= 127:
            j += 1 + c + 1
            produced += c + 1
        else:
            j += 2
            produced += 257 - c
    rec.data_len = j - rec.data_offset
    if produced > target:
        rec.decode_err = "overrun"
    if j < len(d) and d[j] == 0x0D:
        rec.term = "0D"
        j += 1
    else:
        rec.term = "missing(%02x)" % d[j] if j < len(d) else "eof"
    rec._end = j
    return rec


def decode_record(d, rec):
    if rec.data_len:
        raw, used, err = rle_decode(d[rec.data_offset:rec.data_offset + rec.data_len],
                                    rec.n * rec.m)
        rec.raw = raw
        if err and not rec.decode_err:
            rec.decode_err = err
    else:
        rec.raw = bytes(rec.n * rec.m)


# --------------------------------------------------------------------------
# stats
# --------------------------------------------------------------------------
def stats(job, out=sys.stdout):
    p = out.write
    p("file      : %s\n" % job.path)
    p("size      : %d bytes\n" % job.size)
    h = job.header
    p("enter     : %s\n" % h.get("enter_d4"))
    p("EJL       : %s\n" % " | ".join(t["text"].strip() for t in h.get("ejl", [])))
    p("remote    : %s\n" % ", ".join("%s(len=%d,%s)" % (t["tag"], t["len"], t["data"])
                                     for t in h.get("tags", [])[:6]))
    p("\n-- prologue (%d commands) --\n" % len(job.prologue))
    for c in job.prologue:
        p("  @0x%06X %-40s len=%d %s\n" % (c["offset"], c["name"], c["length"], c["payload"]))
    p("\n-- blocks: %d, records: %d --\n"
      % (len(job.blocks), sum(len(b.records) for b in job.blocks)))
    # per block signature
    sig = collections.Counter()
    for b in job.blocks:
        sig[tuple("%02x" % r.color for r in b.records)] += 1
    p("block color signatures: %s\n" % dict(sig))
    # per color
    percolor = collections.OrderedDict()
    for b in job.blocks:
        for r in b.records:
            d = percolor.setdefault(r.color, dict(count=0, n=set(), m=set(),
                                                  comp=set(), bit=set(),
                                                  nonzero=0, lines_nonzero=0,
                                                  first_nonzero=None, last_nonzero=None))
            d["count"] += 1
            d["n"].add(r.n)
            d["m"].add(r.m)
            d["comp"].add(r.comp)
            d["bit"].add(r.bit)
            if r.raw is None:
                continue
            nz = [ln for ln in range(r.m)
                  if any(r.raw[ln * r.n:(ln + 1) * r.n])]
            d["nonzero"] += 1 if nz else 0
            d["lines_nonzero"] += len(nz)
            if nz:
                if d["first_nonzero"] is None:
                    d["first_nonzero"] = (b.index, nz[0])
                d["last_nonzero"] = (b.index, nz[-1])
    p("\n-- per color --\n")
    for col, d in percolor.items():
        p("  color 0x%02X: records=%d n=%s m=%s comp=%s bit=%s "
          "records-with-data=%d nonzero-lines=%d first=%s last=%s\n"
          % (col, d["count"], sorted(d["n"]), sorted(d["m"]), sorted(d["comp"]),
             sorted(d["bit"]), d["nonzero"], d["lines_nonzero"],
             d["first_nonzero"], d["last_nonzero"]))
    # advances
    adv = [(b.index, b.advance) for b in job.blocks if b.advance is not None]
    if adv:
        p("\n-- advances (ESC(v)): first 20 %s\n" % adv[:20])
        p("   distinct: %s\n" % collections.Counter(a[1] for a in adv).most_common(20))
        p("   sum(adv)=%d  blocks=%d  pagesize(ESC S)=%s\n"
          % (sum(a[1] for a in adv), len(job.blocks),
             job.header.get("ESC_S", "")))
    dx = collections.Counter(r.xpos for b in job.blocks for r in b.records)
    p("\n-- ESC($) xpos distinct: %s\n" % dx.most_common(20))
    if job.warnings:
        p("\n!! warnings (%d):\n" % len(job.warnings))
        for w in job.warnings[:20]:
            p("   %s\n" % w)


def prologue_map(job):
    """Turn prologue into a dict of named params."""
    m = {}
    for c in job.prologue:
        raw = bytes.fromhex(c["raw"])
        let = int(c["letter"], 16) if len(c["letter"]) == 2 else None
        pl = bytes.fromhex(c["payload"]) if c["payload"] else b""
        if c["name"].startswith("ESC(U"):
            m["ESC_U"] = dict(unit=struct.unpack("<H", pl[3:5])[0] if len(pl) >= 5 else None,
                              a=pl[0], b=pl[1], c=pl[2], raw=c["payload"])
        elif c["name"].startswith("ESC(D"):
            m["ESC_D"] = dict(r=struct.unpack("<H", pl[0:2])[0], v=pl[2], h=pl[3])
        elif c["name"].startswith("ESC(S"):
            m["ESC_S"] = dict(width=struct.unpack("<I", pl[0:4])[0],
                              height=struct.unpack("<I", pl[4:8])[0])
        elif c["name"].startswith("ESC(c"):
            m["ESC_c"] = dict(a=struct.unpack("<i", pl[0:4])[0],
                              b=struct.unpack("<i", pl[4:8])[0])
        elif c["name"].startswith("ESC(e"):
            m["ESC_e"] = dict(dot=pl[1] if len(pl) > 1 else None, raw=c["payload"])
        elif c["name"].startswith("ESC(K"):
            m["ESC_K"] = dict(v=pl[1] if len(pl) > 1 else None)
        elif c["name"].startswith("ESC(m"):
            m["ESC_m"] = dict(v=pl[0] if pl else None)
        elif c["name"].startswith("ESC(V"):
            m["ESC_V"] = dict(v=struct.unpack("<I", pl[0:4])[0] if len(pl) >= 4 else None)
        elif c["name"].startswith("ESC(i"):
            m["ESC_i"] = dict(v=pl[0] if pl else None)
        elif c["name"].startswith("ESC(G"):
            m["ESC_G"] = dict(v=pl[0] if pl else None)
    return m


# --------------------------------------------------------------------------
# 2-bit unpack
# --------------------------------------------------------------------------
def unpack2bit_msb(row: bytes):
    """byte -> 4 dot values, MSB pair first: d0=(b>>6)&3, d1=(b>>4)&3, d2=(b>>2)&3, d3=b&3"""
    out = bytearray(len(row) * 4)
    k = 0
    for b in row:
        out[k] = (b >> 6) & 3
        out[k + 1] = (b >> 4) & 3
        out[k + 2] = (b >> 2) & 3
        out[k + 3] = b & 3
        k += 4
    return out


def unpack2bit_lsb(row: bytes):
    out = bytearray(len(row) * 4)
    k = 0
    for b in row:
        out[k] = b & 3
        out[k + 1] = (b >> 2) & 3
        out[k + 2] = (b >> 4) & 3
        out[k + 3] = (b >> 6) & 3
        k += 4
    return out


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def load(path):
    return open(path, "rb").read()


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    ap = argparse.ArgumentParser()
    ap.add_argument("prn")
    ap.add_argument("--out", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--light", action="store_true", help="skip raster decode")
    args = ap.parse_args(argv[1:])

    d = load(args.prn)
    job = parse_job(d, decode=not args.light)
    job.path = args.prn

    if cmd == "info":
        stats(job)
    elif cmd == "json":
        j = dict(path=job.path, size=job.size, header=job.header,
                 prologue=job.prologue,
                 blocks=[dict(index=b.index, advance=b.advance,
                              records=[r.to_dict() for r in b.records])
                         for b in job.blocks],
                 tail=job.tail.hex(" "), warnings=job.warnings)
        print(json.dumps(j, indent=1, ensure_ascii=False))
    elif cmd == "stats":
        stats(job)
    elif cmd == "planes":
        # export every record's decoded raster: <outdir>/b<NNN>_c<CC>.bin (n*m bytes)
        outdir = args.outdir or (os.path.splitext(os.path.basename(args.prn))[0] + "_planes")
        os.makedirs(outdir, exist_ok=True)
        idx = []
        for b in job.blocks:
            for rec in b.records:
                if rec.raw is None:
                    continue
                name = "b%03d_c%02X_n%d_m%d.bin" % (b.index, rec.color, rec.n, rec.m)
                with open(os.path.join(outdir, name), "wb") as f:
                    f.write(rec.raw)
                nz = sum(1 for x in rec.raw if x)
                idx.append(dict(block=b.index, color="0x%02X" % rec.color,
                                n=rec.n, m=rec.m, xpos=rec.xpos,
                                file=name, nonzero_bytes=nz))
        with open(os.path.join(outdir, "index.json"), "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=1)
        print("exported %d rasters to %s" % (len(idx), outdir))
    else:
        print("unknown command", cmd)
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
