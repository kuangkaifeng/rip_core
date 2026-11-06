# -*- coding: utf-8 -*-
"""Lead 的快速 ESC/P2 结构探测器（只做统计，不追求完整解析）。
用法: python lead_geom.py <prn>
"""
import sys, struct, collections

def decode_rle(buf, j, need):
    dec = bytearray()
    n = len(buf)
    while j < n and len(dec) < need:
        c = buf[j]
        if c <= 127:
            cnt = c + 1
            dec += buf[j+1:j+1+cnt]
            j += 1 + cnt
        else:
            cnt = 257 - c
            if j + 1 >= n:
                break
            dec += bytes([buf[j+1]]) * cnt
            j += 2
    return bytes(dec[:need]), j

def parse(path):
    buf = open(path, 'rb').read()
    print("file=%s size=%d" % (path, len(buf)))
    pos = 0
    records = []   # dict
    advances = []
    block = 0
    pending_dollar = 0
    while True:
        i = buf.find(b'\x1b', pos)
        if i < 0 or i + 2 >= len(buf):
            break
        b1 = buf[i+1]
        if b1 == 0x69 and i + 9 <= len(buf):
            color = buf[i+2]; comp = buf[i+3]; depth = buf[i+4]
            nl, nh, ml, mh = buf[i+5], buf[i+6], buf[i+7], buf[i+8]
            n = nl | (nh << 8); m = ml | (mh << 8)
            need = n * m
            raw, j = decode_rle(buf, i + 9, need)
            records.append(dict(block=block, color=color, comp=comp, depth=depth,
                                n=n, m=m, dollar=pending_dollar, raw=raw))
            pending_dollar = 0
            pos = j
        elif b1 == 0x28 and i + 5 <= len(buf):
            cmd = buf[i+2]
            ln = buf[i+3] | (buf[i+4] << 8)
            data = buf[i+5:i+5+ln]
            if cmd == 0x24 and len(data) >= 4:      # ESC ( $ horizontal
                pending_dollar = struct.unpack('<I', data[:4])[0]
            elif cmd == 0x76 and len(data) >= 4:    # ESC ( v vertical advance
                advances.append(struct.unpack('<I', data[:4])[0])
                block += 1
            pos = i + 5 + ln
        else:
            pos = i + 1

    print("records=%d advances(blocks-1)=%d distinct colors=%s"
          % (len(records), len(advances), sorted({r['color'] for r in records})))
    if not records:
        return
    print("n values:", collections.Counter(r['n'] for r in records).most_common(6))
    print("m values:", collections.Counter(r['m'] for r in records).most_common(6))
    print("depth:", collections.Counter(r['depth'] for r in records).most_common(6))
    print("dollar:", collections.Counter(r['dollar'] for r in records).most_common(8))
    print("advances:", collections.Counter(advances).most_common(8))
    perblock = collections.Counter(r['block'] for r in records)
    print("records/block:", collections.Counter(perblock.values()).most_common(6))
    print("blocks:", min(perblock), "..", max(perblock), "count=", len(perblock))
    # 每块首记录
    first = [r for r in records if r['block'] == 0]
    r0 = first[0]
    n, m, raw, color = r0['n'], r0['m'], r0['raw'], r0['color']
    print("block0 color=%#x n=%d m=%d" % (color, n, m))
    nz_rows = []
    for y in range(m):
        line = raw[y*n:(y+1)*n]
        nz = sum(1 for v in line if v)
        if nz:
            firstx = next(k for k, v in enumerate(line[:n]) if v)
            nz_rows.append((y, nz, firstx))
    print("block0 data rows: %s" % (nz_rows[:20],))
    # 每块有数据的行数（color=first color only）
    print("per-block nonzero row counts (first 12 blocks):")
    for b in range(min(12, max(perblock) + 1)):
        rr = [r for r in records if r['block'] == b]
        if not rr:
            continue
        rr0 = rr[0]
        n2, m2 = rr0['n'], rr0['m']
        cnt = 0
        rows = []
        for y in range(m2):
            line = rr0['raw'][y*n2:(y+1)*n2]
            if any(line):
                cnt += 1
                rows.append(y)
        print("  block %d color %#x: nonzero_rows=%d rows=%s" % (b, rr0['color'], cnt, rows[:12]))

if __name__ == '__main__':
    parse(sys.argv[1])
