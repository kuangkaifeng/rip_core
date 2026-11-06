# -*- coding: utf-8 -*-
"""Lead: coverage map for page rows -> (block,row) using p = pos + 8r + delta."""
import struct, collections

PRN = r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\data\1793946733280.prn"

def parse_advances(path):
    buf = open(path, 'rb').read()
    adv = []
    pos = 0
    while True:
        i = buf.find(b'\x1b\x28\x76', pos)
        if i < 0 or i + 9 > len(buf): break
        ln = buf[i+3] | (buf[i+4] << 8)
        data = buf[i+5:i+5+ln]
        if ln >= 4:
            adv.append(struct.unpack('<I', data[:4])[0])
        pos = i + 5 + ln
    # 第一个 ESC(v 出现在第一条记录之前，代表 block0 起点
    return adv

adv = parse_advances(PRN)
print("advances:", adv[:5], "... total", len(adv))
# block k 起点位置（单位 1/720 英寸）
# 观察：adv[0]=150 是 block0 起点；之后 adv[1..]=79 是相邻块推进
pos = []
p = adv[0]
pos.append(p)
for a in adv[1:]:
    p += a
    pos.append(p)
print("num blocks", len(pos), "pos range", pos[0], pos[-1])

NROW = 90
SPACING = 8
cover = collections.defaultdict(list)
for k, pk in enumerate(pos):
    for r in range(NROW):
        cover[pk + SPACING*r].append((k, r))

print("covered page rows:", len(cover), "range", min(cover), max(cover))
# 内容区间：假设图像 654 行、P0=645 → 页面行 645..4569
lo, hi = 645, 645 + 654*6
missing = [p for p in range(lo, hi) if p not in cover]
multi = [p for p in range(lo, hi) if len(cover.get(p, [])) > 1]
print("content page rows %d..%d: missing=%d multi=%d" % (lo, hi, len(missing), len(multi)))
print("missing sample:", missing[:20])
print("multi sample:", [(p, cover[p][:4]) for p in multi[:5]])
# 每个 block 实际覆盖的页面行范围
for k in (0, 1, 5, 6, 7, 8, 20, 24, 48):
    ps = [pos[k] + SPACING*r for r in range(NROW)]
    print("block %2d pos=%4d rows p=[%d..%d]" % (k, pos[k], ps[0], ps[-1]))
