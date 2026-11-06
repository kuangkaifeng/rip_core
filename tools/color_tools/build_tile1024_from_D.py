# -*- coding: utf-8 -*-
"""从 T1 的 176x176 探针 D 场 bin 直接构建 1024x1024 四通道加网 tile。

输入: work/protocol/evidence/probe_scan_D_{C,M,Y,K}176.bin
      格式: uint16 LE x N (N=2,090,880 = 22 blocks * 90 rows * 1056 px)；
            0..255 = D，0xFFFF = microweave 空白填充位置。
      光栅顺序：block-major -> record-major -> row-major，4px/byte LSB-first。
几何: 176px@120dpi -> mode2 内容 1056x1056 页面像素；blocks=22，adv=79，pos_k=79k；
      page_row = pos_k + 8*r；内容行 i = page_row - 640；内容列 x = 1056 内像素。
      D 按内容相对坐标 1024 周期：tile[i%1024][x%1024]。
输出: reference/screen/engine1024/thr_{C,M,Y,K}.bin (1024*1024*3, 每像素 [T1,T2,T3])
      + screen_meta.json
"""
import os, json, struct

WS = r"D:\work\RIP核心分析"
EV = os.path.join(WS, "work", "protocol", "evidence")
OUT = os.path.join(WS, "reference", "screen", "engine1024")
os.makedirs(OUT, exist_ok=True)

N = 2_090_880
BLOCKS = 22
ROWS = 90
COLS = 1056
P0 = 640
ADV = 79
VSTEP = 8
SIZE = 1024
FILL = 0xFFFF

CH = {"C": "probe_scan_D_C176.bin", "M": "probe_scan_D_M176.bin",
      "Y": "probe_scan_D_Y176.bin", "K": "probe_scan_D_K176.bin"}
# 各通道内容顶行（页面行）：C/K=640，M/Y=644（实测，见 docs/prn_escp2.md）
TOP = {"C": 640, "M": 644, "Y": 644, "K": 640}


def build_tile(fname, top):
    raw = open(os.path.join(EV, fname), "rb").read()
    assert len(raw) == N * 2, (fname, len(raw))
    D = struct.unpack("<%dH" % N, raw)
    tile = [None] * (SIZE * SIZE)
    filled = 0
    for k in range(BLOCKS):
        pos = ADV * k
        for r in range(ROWS):
            p = pos + VSTEP * r
            i = p - top
            if not (0 <= i < COLS):
                continue
            ty = i % SIZE
            base = (k * ROWS + r) * COLS
            for j in range(COLS):
                d = D[base + j]
                if d == FILL or d > 255:
                    continue
                # 4px/byte LSB-first 索引 -> 物理 x（PRN 为 MSB-first）
                x = (j >> 2) * 4 + (3 - (j & 3))
                if x >= COLS:
                    continue
                tx = x % SIZE
                idx = ty * SIZE + tx
                if tile[idx] is None:
                    tile[idx] = d
                    filled += 1
    # 对未填位置用邻近填充（环形搜索）
    missing = [i for i in range(SIZE * SIZE) if tile[i] is None]
    for idx in missing:
        y, x = divmod(idx, SIZE)
        found = None
        for rad in range(1, 17):
            for dy in (-rad, 0, rad):
                for dx in (-rad, 0, rad):
                    if dy == 0 and dx == 0:
                        continue
                    j = ((y + dy) % SIZE) * SIZE + ((x + dx) % SIZE)
                    if tile[j] is not None:
                        found = tile[j]
                        break
                if found is not None:
                    break
            if found is not None:
                break
        tile[idx] = found if found is not None else 129
    print("%s: filled=%d missing=%d (%.3f%%)" %
          (fname, filled, len(missing), 100.0 * len(missing) / (SIZE * SIZE)))
    return tile


def thr_for(D):
    """level=(3v+D)>>8 的等价阈值: Ti = ceil((256i-D)/3)"""
    out = bytearray(SIZE * SIZE * 3)
    for i, d in enumerate(D):
        if d is None:
            d = 129
        out[i * 3 + 0] = min(255, (256 - d + 2) // 3) if d <= 256 else 0
        out[i * 3 + 1] = min(255, (512 - d + 2) // 3)
        out[i * 3 + 2] = min(255, (768 - d + 2) // 3)
    return bytes(out)


meta = {"version": 4, "size": SIZE, "tile_size": SIZE,
        "engine_rule": "level(v,x,y)=(v>=T1)+(v>=T2)+(v>=T3); thr_<ink>.bin = size*size*3 bytes raster y*size+x",
        "coordinate_indexing": {"type": "content-relative",
                                "tile": "D(x,y)=TILE[x%1024][y%1024]"},
        "source": "probe_scan_{C,M,Y,K}###_176_a3dtf1390_m2.prn (256 levels each, 176x176 CMYK probes)",
        "content_top_page_row": {"C": 640, "M": 644, "Y": 644, "K": 640},
        "channels": []}
for ink, fname in CH.items():
    tile = build_tile(fname, TOP[ink])
    data = thr_for(tile)
    fn = "thr_%s.bin" % ink
    open(os.path.join(OUT, fn), "wb").write(data)
    meta["channels"].append({"ink": ink, "file": fn, "phaseX": 0, "phaseY": 0,
                             "content_top_page_row": meta["content_top_page_row"][ink]})
json.dump(meta, open(os.path.join(OUT, "screen_meta.json"), "w", encoding="utf-8"), indent=1)
print("written ->", OUT)
