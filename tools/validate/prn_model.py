#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prn_model.py -- 蒙泰 MainTop ESC/P2 (.prn) 解析 / 页面重建模型 (T5 验证工具)

用途：
  * 解析 A3-DTF-1390 的 ESC/P2 作业（作业头 + 命令区 + 光栅块 + 尾部）
  * 按 "page_row = block_pos + row_step * r" 把每块的光栅行铺回"页面 raster"
  * 支持按 (颜色, 页面行, x) 的冲突检测，用来反推重叠拆分规则
  * 提供 RLE 编解码、2bit 解包、BMP 导出

页面坐标约定（全部为 ESC(U 的 page unit，m2/m3 = 1/720 英寸）：
  page_row  : 自上而下的页面行号
  x         : 行内 dot 列号（720dpi 水平）

本文件只依赖标准库 + 可选 PIL（导出 PNG 预览）。
"""
from __future__ import annotations

import os
import struct
import sys

ESC = 0x1B
ENTER_D4 = bytes([0x00, 0x00, 0x00, 0x1B, 0x01])
REMOTE_EXIT = bytes([0x1B, 0x00, 0x00, 0x00])

# ESC ( <letter> 名称（打印/文档用）
ESC_PAREN_NAMES = {
    0x24: "ESC($)", 0x44: "ESC(D)", 0x53: "ESC(S)", 0x63: "ESC(c)",
    0x55: "ESC(U)", 0x47: "ESC(G)", 0x69: "ESC(i)", 0x4B: "ESC(K)",
    0x65: "ESC(e)", 0x6D: "ESC(m)", 0x56: "ESC(V)", 0x76: "ESC(v)",
    0x52: "ESC(R)", 0x28: "ESC(?)",
}

# 颜色码 -> 我们的设备通道命名（由语料 + prs 色序确定，见 ENGINE_STATUS）
COLOR_NAMES = {
    0x00: "C", 0x04: "K", 0x11: "Y", 0x12: "M",
    0x01: "W1", 0x02: "W2",
}

# ---------------------------------------------------------------------------
# A3-DTF-1390 实测模式参数表（docs/prn_escp2.md §7.2 §8）
#   page_unit : 1 page unit = 1/page_unit inch
#   vstep     : 块内相邻光栅行的纸行距（page unit）
#   P0        : 图像第 0 行对应的纸行（模式常量）
#   M         : ESC(c)/ESC(S) 页边距常数
#   adv       : 块推进（ESC(v)）
#   colors    : 每块记录顺序
#   offsets   : 每记录纵向偏移（page unit，物理头色行错位；记录坐标 = 物理纸行 + off）
#   white_adv : 全零作业尾部 ESC(v)（实测模式常量）
# ---------------------------------------------------------------------------
MODE_TABLE = {
    0: dict(page_unit=360, vstep=4, M=245, P0=288, adv=71, hdpi=720, vdpi=360,
            colors=[0x04, 0x00, 0x12, 0x11], offsets=[0, 0, 2, 2],
            white_adv=353, dotsize=0x21, method=0x41, uh=4),
    1: dict(page_unit=360, vstep=4, M=277, P0=324, adv=35, hdpi=720, vdpi=360,
            colors=[0x12, 0x11, 0x00, 0x02, 0x01, 0x04], offsets=[2, 2, 0, 0, 2, 2],
            white_adv=349, dotsize=0x21, method=0x41, uh=4),
    2: dict(page_unit=720, vstep=8, M=555, P0=640, adv=79, hdpi=720, vdpi=720,
            colors=[0x04, 0x00, 0x12, 0x11], offsets=[0, 0, 4, 4],
            white_adv=705, dotsize=0x21, method=0x41, uh=4),
    3: dict(page_unit=720, vstep=8, M=587, P0=680, adv=39, hdpi=720, vdpi=720,
            colors=[0x12, 0x11, 0x00, 0x02, 0x01, 0x04], offsets=[4, 4, 0, 0, 4, 4],
            white_adv=697, dotsize=0x21, method=0x41, uh=4),
    5: dict(page_unit=720, vstep=8, M=627, P0=712, adv=11, hdpi=360, vdpi=720,
            colors=[0x12, 0x11, 0x00, 0x02, 0x01, 0x04], offsets=[4, 4, 0, 0, 4, 4],
            white_adv=0, dotsize=0x34, method=0x40, uh=2),
    7: dict(page_unit=1440, vstep=16, M=1227, P0=1413, adv=11, hdpi=360, vdpi=1440,
            colors=[0x12, 0x11, 0x00, 0x02, 0x01, 0x04], offsets=[8, 8, 0, 0, 8, 8],
            white_adv=0, dotsize=0x34, method=0x40, uh=2),
    9: dict(page_unit=1440, vstep=16, M=1227, P0=1413, adv=11, hdpi=720, vdpi=1440,
            colors=[0x12, 0x11, 0x00, 0x02, 0x01, 0x04], offsets=[8, 8, 0, 0, 8, 8],
            white_adv=0, dotsize=0x21, method=0x51, uh=1),
}


def mode_params(prn):
    """由命令区推导 modeId 及几何参数；返回 (modeId, dict)。"""
    cp = cmd_params(prn)
    page_unit = cp.get("page_dpi", 720)
    props = prn.block_colors() if prn.blocks else []
    planes = len(props) if props else 0
    raster_h = cp.get("raster_h", 2)
    mode = None
    if page_unit == 720:
        mode = 5 if (planes == 6 and raster_h == 4) else (3 if planes == 6 else 2)
    elif page_unit == 360:
        mode = 1 if planes == 6 else 0
    elif page_unit == 1440:
        mode = 7 if raster_h == 4 else 9
    if mode not in MODE_TABLE:
        mode = 2
    return mode, MODE_TABLE[mode]


def solve_block_row(mp, p, pos0=0, max_block=None):
    """纸行 p -> (block,row)；k 为满足 pos_k≡p(mod vstep)、pos_k≤p、r≤89 的最大 k。

    与 C++ layout_escp2.cpp 的 solveBlockRow 完全同构（用于独立验证）。
    """
    adv, vstep, rows = mp["adv"], mp["vstep"], 90
    rel = p - pos0
    if rel < 0:
        return None
    inv = pow(adv % vstep, -1, vstep) if vstep > 1 else 0
    k0 = (rel % vstep) * inv % vstep
    kmax = rel // adv
    if max_block is not None and kmax > max_block:
        kmax = max_block
    if kmax < k0:
        return None
    k = k0 + ((kmax - k0) // vstep) * vstep
    while k >= 0:
        r = (rel - adv * k) // vstep
        if 0 <= r < rows:
            return (k, r)
        if r >= rows:
            return None
        k -= vstep
    return None


def extract_content_planes(prn, mode_id=None, initial_pos=None):
    """PRN -> 内容平面（与 C++ extractContentPlanes 同构）。

    返回 (planes, W, H, info)：
      planes[c] = bytearray(W*H)，值 0..3，c 按 mode 的颜色记录顺序
      W = content_w_dots，H = content_h_units
    """
    if mode_id is None:
        mode_id, mp = mode_params(prn)
    else:
        mp = MODE_TABLE[mode_id]
    cp = cmd_params(prn)
    content_h = cp.get("page_top", 0) + cp.get("page_margin", 0)  # pageFormatB + pageFormatA
    content_w_units = cp.get("page_w", 0)
    W = int(round(content_w_units * mp["hdpi"] / mp["page_unit"]))
    H = int(content_h)
    P0 = mp["P0"]
    rs = mp["vstep"]
    pos0 = prn.assign_positions(initial_pos)
    nrec = len(mp["colors"])
    planes = [bytearray(W * H) for _ in range(nrec)]
    if not prn.blocks:
        return planes, W, H, dict(mp=mp, modeId=mode_id, pos0=pos0, content_w_units=content_w_units)
    m = prn.block_rows()
    for k, blk in enumerate(prn.blocks):
        for ri, rec in enumerate(blk.records):
            if ri >= nrec:
                continue
            off = mp["offsets"][ri]
            pl = planes[ri]
            for r in range(rec.m):
                content_row = blk.pos + rs * r - off - P0
                if content_row < 0 or content_row >= H:
                    continue
                line = rec.raw[r * rec.n:(r + 1) * rec.n]
                dots = unpack2bit(line)
                base = content_row * W
                lim = min(W, len(dots))
                for x in range(lim):
                    v = dots[x]
                    if v > pl[base + x]:
                        pl[base + x] = v
    rows = max((b.pos + rs * (m - 1) for b in prn.blocks), default=0)
    info = dict(mp=mp, modeId=mode_id, pos0=pos0, content_w_units=content_w_units,
                content_h_units=content_h, page_rows=rows)
    return planes, W, H, info


# ---------------------------------------------------------------------------
# RLE (ESC/P2 comp=1)
# ---------------------------------------------------------------------------
def rle_decode(data: bytes, expected: int, pos: int = 0):
    """从 data[pos] 开始解码 expected 字节。返回 (raw, consumed_bytes, err)。

    count = c; c<=127 -> 复制 (c+1) 字节; c>=128 -> 下一字节重复 (257-c) 次。
    """
    out = bytearray()
    i = pos
    n = len(data)
    while len(out) < expected:
        if i >= n:
            return bytes(out), i - pos, "eof"
        c = data[i]
        i += 1
        if c <= 127:
            cnt = c + 1
            if i + cnt > n:
                return bytes(out), i - pos, "literal-overrun"
            out += data[i:i + cnt]
            i += cnt
        else:
            cnt = 257 - c
            if i >= n:
                return bytes(out), i - pos, "repeat-missing"
            out += bytes([data[i]]) * cnt
            i += 1
    return bytes(out), i - pos, None


def rle_encode_line(line: bytes) -> bytes:
    """单行 RLE 编码（蒙泰实测规则）：
       * 连续相同字节 >=2 用 repeat token（最多 128 个）
       * 字面量段最多 128 字节，遇到 >=2 的 run 就断开
    """
    out = bytearray()
    i = 0
    n = len(line)
    while i < n:
        run = 1
        while i + run < n and line[i + run] == line[i] and run < 128:
            run += 1
        if run >= 2:
            out.append((257 - run) & 0xFF)
            out.append(line[i])
            i += run
        else:
            start = i
            while i < n:
                if i + 1 < n:
                    nr = 1
                    while i + nr < n and line[i + nr] == line[i] and nr < 128:
                        nr += 1
                    if nr >= 2:
                        break
                i += 1
                if i - start >= 128:
                    break
            cnt = i - start
            if cnt:
                out.append((cnt - 1) & 0xFF)
                out += line[start:i]
    return bytes(out)


def rle_encode(raw: bytes, line_bytes: int) -> bytes:
    out = bytearray()
    for off in range(0, len(raw), line_bytes):
        out += rle_encode_line(raw[off:off + line_bytes])
    return bytes(out)


# ---------------------------------------------------------------------------
# 2bit 解包 / 打包
# ---------------------------------------------------------------------------
def unpack2bit(row: bytes):
    """MSB-first: 每字节 4 个 dot（2bit），高 2bit 是行内更靠左的像素。"""
    out = bytearray(len(row) * 4)
    k = 0
    for b in row:
        out[k] = (b >> 6) & 3
        out[k + 1] = (b >> 4) & 3
        out[k + 2] = (b >> 2) & 3
        out[k + 3] = b & 3
        k += 4
    return out


def pack2bit(dots) -> bytes:
    out = bytearray((len(dots) + 3) // 4)
    for i, v in enumerate(dots):
        out[i >> 2] |= (v & 3) << (6 - 2 * (i & 3))
    return bytes(out)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
class Record(object):
    __slots__ = ("color", "comp", "bit", "n", "m", "xpos", "offset",
                 "data_offset", "data_len", "raw", "term", "err", "_end")

    def __init__(self):
        self.color = 0
        self.comp = 0
        self.bit = 0
        self.n = 0
        self.m = 0
        self.xpos = 0
        self.offset = 0
        self.data_offset = 0
        self.data_len = 0
        self.raw = None
        self.term = None
        self.err = None


class Block(object):
    __slots__ = ("index", "advance", "v_offset", "records", "pos")

    def __init__(self, index):
        self.index = index
        self.advance = None       # 该块之前的 ESC(v 参数（首块可能 None -> 0 或 prologue 值）
        self.v_offset = 0
        self.records = []
        self.pos = 0


class Prn(object):
    def __init__(self):
        self.path = None
        self.size = 0
        self.header = {}
        self.cmds = []            # [(letter/int, payload bytes, offset)]
        self.first_record_offset = 0
        self.blocks = []
        self.tail = b""
        self.warnings = []

    # ---- 便捷访问 ----
    def cmd(self, letter):
        for item in self.cmds:
            if item[0] == letter:
                return item[1]
        return None

    def tag(self, name):
        return self.header.get("tags", {}).get(name)

    def tag_text(self, name):
        d = self.tag(name)
        return d.decode("latin1") if d else None

    # ---- 位置 ----
    def assign_positions(self, initial_pos=None):
        """块绝对位置 = 块前所有 ESC(v 累计（含 prologue 里首块之前的 ESC(v)）。

        initial_pos 为 None 时自动从 prologue 的 ESC(v 求和（通常 0 或一个初值）。
        返回 initial 值。
        """
        if initial_pos is None:
            initial_pos = 0
            for letter, payload, off in self.cmds:
                # 只累计"首条记录之前"的 ESC(v（raster 区内每块前的 ESC(v 不算初值）
                if letter == 0x76 and off < self.first_record_offset and len(payload) >= 4:
                    initial_pos += struct.unpack("<I", payload[:4])[0]
        pos = initial_pos
        for b in self.blocks:
            if b.advance:
                pos += b.advance
            b.pos = pos
        return initial_pos

    # ---- 页面映射 ----
    def row_cover(self, row_step):
        """返回 dict: page_row -> [(block_index, raster_row)]"""
        cover = {}
        for blk in self.blocks:
            for r in range(self.block_rows()):
                p = blk.pos + row_step * r
                cover.setdefault(p, []).append((blk.index, r))
        return cover

    def block_rows(self):
        for blk in self.blocks:
            if blk.records:
                return blk.records[0].m
        return 0

    def block_colors(self):
        """块内记录的颜色顺序（取第一个块）。"""
        if not self.blocks:
            return []
        return [r.color for r in self.blocks[0].records]

    def records_of(self, block_index, color):
        for r in self.blocks[block_index].records:
            if r.color == color:
                return r
        return None

    def dot_levels(self):
        """全文件出现过的 dot 值集合。"""
        vals = set()
        for blk in self.blocks:
            for rec in blk.records:
                if rec.raw:
                    vals.update(rec.raw)
        if 0 in vals:
            vals.discard(0)
        out = set()
        for v in vals:
            out.update((v >> 6) & 3, (v >> 4) & 3, (v >> 2) & 3, v & 3)
        out.discard(0)
        return out


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------
def _parse_remote(d, pos):
    """解析 ESC ( R 08 00 00 REMOTE1 + 标签记录，返回 (tags, pos)。"""
    tags = {}
    order = []
    # ESC ( R 08 00 <data: 00 "REMOTE1">
    if d[pos:pos + 5] != bytes([ESC, 0x28, 0x52, 0x08, 0x00]):
        raise ValueError("expected ESC(R remote enter at 0x%X" % pos)
    if d[pos + 6:pos + 13] != b"REMOTE1":
        raise ValueError("expected REMOTE1 at 0x%X" % (pos + 6))
    pos += 13
    while pos + 4 <= len(d):
        if d[pos:pos + 4] == REMOTE_EXIT:
            pos += 4
            break
        tag = d[pos:pos + 2].decode("latin1")
        ln = d[pos + 2] | (d[pos + 3] << 8)
        data = d[pos + 4:pos + 4 + ln]
        tags.setdefault(tag, []).append(data)
        order.append((tag, data))
        pos += 4 + ln
    return {"tags": tags, "order": order}, pos


def _parse_one_record(d, i):
    """解析 i 处的 ESC i + RLE + 0D，返回 Record。"""
    rec = Record()
    rec.offset = i
    rec.color = d[i + 2]
    rec.comp = d[i + 3]
    rec.bit = d[i + 4]
    rec.n = d[i + 5] | (d[i + 6] << 8)
    rec.m = d[i + 7] | (d[i + 8] << 8)
    need = rec.n * rec.m
    rec.data_offset = i + 9
    j = rec.data_offset
    produced = 0
    while produced < need and j < len(d):
        c = d[j]
        if c <= 127:
            produced += c + 1
            j += 1 + c + 1
        else:
            produced += 257 - c
            j += 2
    rec.data_len = j - rec.data_offset
    if produced != need:
        rec.err = "rle-length %d != %d" % (produced, need)
    if j < len(d) and d[j] == 0x0D:
        rec.term = "0D"
        j += 1
    else:
        rec.term = "missing"
    rec.raw, _used, err = rle_decode(d, need, rec.data_offset)
    if err and not rec.err:
        rec.err = err
    rec._end = j
    return rec


def parse_prn(path, decode=True):
    d = open(path, "rb").read()
    prn = Prn()
    prn.path = path
    prn.size = len(d)
    if d[:5] != ENTER_D4:
        raise ValueError("not an ESC/P2 EJL job: %s" % d[:8].hex(" "))
    pos = 5
    ejl = []
    while pos < len(d) and d[pos:pos + 1] == b"@":
        e = d.find(b"\n", pos)
        if e < 0:
            raise ValueError("unterminated @EJL")
        ejl.append(d[pos:e + 1].decode("latin1"))
        pos = e + 1
        if len(ejl) >= 2:
            break
    prn.header["ejl"] = ejl
    prn.header["remote"], pos = _parse_remote(d, pos)

    # ---- 命令区（到第一条 ESC ( $ 或 ESC i 为止）----
    while pos < len(d):
        if d[pos] != ESC:
            prn.warnings.append("unexpected 0x%02X in cmd region @0x%X" % (d[pos], pos))
            break
        c2 = d[pos + 1]
        if c2 == 0x28:
            letter = d[pos + 2]
            if letter in (0x24, 0x76):   # ESC($ 或 ESC(v -> 进入 raster 区
                break
            ln = d[pos + 3] | (d[pos + 4] << 8)
            prn.cmds.append((letter, d[pos + 5:pos + 5 + ln], pos))
            pos += 5 + ln
        elif c2 == 0x40:
            prn.cmds.append((0x40, b"", pos))
            pos += 2
        elif c2 == 0x55:
            prn.cmds.append((0x55, d[pos + 2:pos + 3], pos))
            pos += 3
        else:
            # 未知（例如 ESC(V 是 ESC( 形式，不属于这里）
            prn.warnings.append("unknown ESC %02X in cmd region @0x%X" % (c2, pos))
            pos += 2
    prn.first_record_offset = pos

    # ---- raster 区 ----
    pending_adv = None     # (value, offset)
    block = None
    while pos < len(d):
        if d[pos] == 0x0C:
            prn.tail = d[pos:]
            break
        if d[pos] != ESC:
            prn.warnings.append("stray 0x%02X @0x%X in raster" % (d[pos], pos))
            pos += 1
            continue
        c2 = d[pos + 1]
        if c2 == 0x28:
            letter = d[pos + 2]
            ln = d[pos + 3] | (d[pos + 4] << 8)
            payload = d[pos + 5:pos + 5 + ln]
            if letter == 0x76:      # ESC(v -> 新块
                if block is not None and block.records:
                    prn.blocks.append(block)
                    block = None
                pending_adv = (struct.unpack("<I", payload[:4])[0], pos)
                prn.cmds.append((0x76, payload, pos))
                pos += 5 + ln
                continue
            if letter == 0x24:      # ESC($ 绝对水平位置
                xpos = struct.unpack("<I", payload[:4])[0] if len(payload) >= 4 else 0
                pos += 5 + ln
                if d[pos:pos + 2] != bytes([ESC, 0x69]):
                    prn.warnings.append("ESC($ not followed by ESC i @0x%X" % pos)
                    continue
                rec = _parse_one_record(d, pos)
                rec.xpos = xpos
                if block is None:
                    block = Block(len(prn.blocks))
                    if pending_adv is not None:
                        block.advance = pending_adv[0]
                        block.v_offset = pending_adv[1]
                        pending_adv = None
                    else:
                        block.v_offset = rec.offset
                block.records.append(rec)
                pos = rec._end
                continue
            # 其它 ESC( 命令出现在 raster 区：记录后跳过
            prn.cmds.append((letter, payload, pos))
            prn.warnings.append("ESC(%02X in raster section @0x%X" % (letter, pos))
            pos += 5 + ln
            continue
        if c2 == 0x69:
            if block is None:
                block = Block(len(prn.blocks))
                if pending_adv is not None:
                    block.advance = pending_adv[0]
                    block.v_offset = pending_adv[1]
                    pending_adv = None
            rec = _parse_one_record(d, pos)
            block.records.append(rec)
            pos = rec._end
            continue
        prn.warnings.append("unknown ESC %02X @0x%X in raster" % (c2, pos))
        pos += 2
    if block is not None and block.records:
        prn.blocks.append(block)
    return prn


# ---------------------------------------------------------------------------
# 命令区参数提炼
# ---------------------------------------------------------------------------
def cmd_params(prn):
    """把命令区解析成几何参数字典。"""
    p = {}
    for letter, data, _off in prn.cmds:
        if letter == 0x55 and len(data) == 5:
            unit = struct.unpack("<H", data[3:5])[0]
            p["unit"] = unit
            p["page_dpi"] = unit // data[0] if data[0] else 0
            p["v_dpi"] = unit // data[1] if data[1] else 0
            p["h_dpi"] = unit // data[2] if data[2] else 0
        elif letter == 0x44 and len(data) == 4:
            r = struct.unpack("<H", data[0:2])[0]
            p["raster_r"] = r
            p["raster_v"] = data[2]
            p["raster_h"] = data[3]
            p["raster_v_dpi"] = r // data[2] if data[2] else 0
            p["raster_h_dpi"] = r // data[3] if data[3] else 0
        elif letter == 0x63 and len(data) == 8:
            p["page_margin"] = struct.unpack("<i", data[0:4])[0]
            p["page_top"] = struct.unpack("<i", data[4:8])[0]
        elif letter == 0x53 and len(data) == 8:
            p["page_w"], p["page_h"] = struct.unpack("<II", data[0:8])
        elif letter == 0x65 and len(data) == 2:
            p["dotsize"] = data[1]
        elif letter == 0x4B and len(data) == 2:
            p["colormode"] = data[1]
        elif letter == 0x6D and len(data) == 1:
            p["method"] = data[0]
        elif letter == 0x47 and len(data) == 1:
            p["graphics"] = data[0]
        elif letter == 0x69 and len(data) == 1:
            p["microweave"] = data[0]
        elif letter == 0x56 and len(data) == 4:
            p["abs_v"] = struct.unpack("<I", data[0:4])[0]
    return p


# ---------------------------------------------------------------------------
# 页面重建
# ---------------------------------------------------------------------------
class PageRaster(object):
    """一页的点阵：colors = {color: bytearray(rows*width)}（每像素 0..3）

    另有 conflict 统计：同一 (page_row, x) 被多个 (block,row) 写入的次数直方图。
    """

    def __init__(self, rows, width, colors):
        self.rows = rows
        self.width = width
        self.colors = colors              # list of color codes
        self.plane = {c: bytearray(rows * width) for c in colors}
        self.count = bytearray(rows * width)   # 写入次数（所有颜色合计）
        self.both = 0                     # 冲突像素数
        self.multis = 0                   # 多覆盖的 (p,x) 数

    def place(self, color, row, x, v, accumulate=False):
        off = row * self.width + x
        pl = self.plane[color]
        if accumulate:
            old = pl[off]
            if old and v:
                self.both += 1
            pl[off] = max(old, v)
        else:
            pl[off] = v
        self.count[off] += 1

    def export_bmp(self, color, path):
        """导出 8bit 灰度 BMP（dot 值 0..3 -> 亮度 255..0），不依赖 PIL。"""
        rows, width = self.rows, self.width
        stride = (width * 3 + 3) & ~3
        data = bytearray()
        for y in range(rows - 1, -1, -1):
            line = bytearray(stride)
            for x in range(width):
                v = 255 - self.plane[color][y * width + x] * 85
                line[x * 3:x * 3 + 3] = bytes([v, v, v])
            data += line
        hdr = bytearray(54)
        hdr[0:2] = b"BM"
        struct.pack_into("<I", hdr, 2, 54 + len(data))
        struct.pack_into("<I", hdr, 10, 54)
        struct.pack_into("<I", hdr, 14, 40)
        struct.pack_into("<i", hdr, 18, width)
        struct.pack_into("<i", hdr, 22, rows)
        struct.pack_into("<H", hdr, 26, 1)
        struct.pack_into("<H", hdr, 28, 24)
        open(path, "wb").write(hdr + data)


def reconstruct(prn, row_step=None, width=None, initial_pos=None,
                accumulate=False, rule=None):
    """把 PRN 铺回页面 raster。

    参数：
      row_step  : 光栅行在页面上的行距（page unit）。None -> 由命令区推导
                  (page_dpi / raster_v_dpi，即 720/90=8 for m2/m3, 360/90=4 for m0/m1)
      width     : 页面 raster 列数。None -> 由记录 n*4 推导
      accumulate: True 时重叠像素取 max 并统计冲突（用于分析），False 时后写覆盖
      rule      : 可选函数 rule(block_index, r, p, x, v) -> bool，决定该像素是否写入

    返回 PageRaster（rows 已按所有块的 p 范围截断）。
    """
    if not prn.blocks:
        return None
    cp = cmd_params(prn)
    if row_step is None:
        row_step = cp.get("page_dpi", 720) // cp.get("raster_v_dpi", 90)
    if width is None:
        width = max(rec.n * 4 for b in prn.blocks for rec in b.records)
    initial = prn.assign_positions(initial_pos)

    # 页面行范围
    rows = 0
    last = 0
    m = prn.block_rows()
    for b in prn.blocks:
        last = max(last, b.pos + row_step * (m - 1))
    rows = last + 18      # 留些余量（页面尾部）

    colors = prn.block_colors()
    page = PageRaster(rows, width, colors)
    page.initial_pos = initial
    page.row_step = row_step
    page.cmd = cp

    for blk in prn.blocks:
        for rec in blk.records:
            if rec.color not in page.plane:
                continue
            n = rec.n
            raw = rec.raw
            for r in range(rec.m):
                p = blk.pos + row_step * r
                line = raw[r * n:(r + 1) * n]
                base = p * width
                pl = page.plane[rec.color]
                cnt = page.count
                for byi, byte in enumerate(line):
                    if not byte:
                        continue
                    x0 = byi * 4
                    if x0 >= width:
                        break
                    for k in range(4):
                        v = (byte >> (6 - 2 * k)) & 3
                        if not v:
                            continue
                        x = x0 + k
                        if x >= width:
                            break
                        if rule is not None and not rule(blk.index, r, p, x, v):
                            continue
                        off = base + x
                        if accumulate:
                            old = pl[off]
                            if old and v:
                                page.both += 1
                            pl[off] = old if old > v else v
                        else:
                            pl[off] = v
                        cnt[off] += 1
    # 统计多覆盖像素
    page.multis = sum(1 for c in page.count if c > 1)
    return page


# ---------------------------------------------------------------------------
# 简单自测
# ---------------------------------------------------------------------------
def _main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    prn = parse_prn(argv[2])
    cp = cmd_params(prn)
    if cmd in ("info", "stats"):
        print("file:", prn.path, "size:", prn.size)
        print("ejl:", prn.header["ejl"])
        print("remote:", [(t, len(d)) for t, d in prn.header["remote"]["order"]])
        print("cmd params:", cp)
        print("blocks:", len(prn.blocks), "records/block:", len(prn.blocks[0].records) if prn.blocks else 0)
        print("colors:", [hex(c) for c in prn.block_colors()])
        print("iconv/n/m:", prn.blocks[0].records[0].n if prn.blocks else None,
              prn.blocks[0].records[0].m if prn.blocks else None)
        print("advances:", [b.advance for b in prn.blocks[1:]][:6], "...",
              "sum:", sum(b.advance or 0 for b in prn.blocks))
        init = prn.assign_positions()
        print("initial_pos:", init, "positions:", [b.pos for b in prn.blocks][:8], "...")
        print("warnings:", prn.warnings[:5])
    elif cmd == "raster":
        page = reconstruct(prn)
        print("rows:", page.rows, "width:", page.width, "both:", page.both, "multis:", page.multis)
        outdir = argv[3] if len(argv) > 3 else "."
        for c in page.colors:
            path = os.path.join(outdir, "plane_%02x.bmp" % c)
            page.export_bmp(c, path)
            print("wrote", path)
    else:
        print("unknown", cmd)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
