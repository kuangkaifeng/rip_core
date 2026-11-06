# -*- coding: utf-8 -*-
# --- header ---
h = r"D:\work\RIP核心分析\src\core\encode\escp2_writer.h"
t = open(h, encoding="utf-8").read()
old = """    // 命令区参数（单位均为 ESC/P2 规定单位）
    int unit = 2880;                // ESC ( U
    int pageDpi = 1440;
    int vDpi = 1440;
    int hDpi = 1440;
    int rasterR = 1440;             // ESC ( D
    int rasterV = 16;
    int rasterH = 4;
    int paperWidth = 5669;          // ESC ( S (1/1440 inch)
    int paperHeight = 4442;
"""
new = """    // 命令区参数（单位均为 ESC/P2 规定单位；实测见 docs/02_geometry_escp2.md）
    int uA = 4, uV = 4, uH = 4;     // ESC ( U 三个比值（2880/比值 = unit/in）
    int rasterR = 1440;             // ESC ( D
    int rasterV = 16;
    int rasterH = 2;
    uint8_t dotSize = 0x21;         // ESC ( e 的墨滴大小字节
    uint16_t colorMode = 2;         // ESC ( K 的 data[1]
    int paperWidth = 0;             // ESC ( S（page unit）
    int paperHeight = 0;
    int pageFormatTop = 0;          // ESC ( c 两个 int32
    int pageFormatBottom = 0;
    int dollarMode = 0;             // ESC ( $ 参数规则：0=恒 0；1=floor(block/16)%4
"""
assert old in t
t = t.replace(old, new)
open(h, "w", encoding="utf-8", newline="").write(t)
print("header patched")

# --- cpp ---
c = r"D:\work\RIP核心分析\src\core\encode\escp2_writer.cpp"
t2 = open(c, encoding="utf-8").read()
# ESC ( U
old_u = """    // ESC ( U 05 00 [unit/page, unit/v, unit/h, unitLo, unitHi]
    putByte(0x1B); putByte(0x28); putByte(0x55); putByte(0x05); putByte(0x00);
    putByte(static_cast<uint8_t>(m_cfg.unit / m_cfg.pageDpi));
    putByte(static_cast<uint8_t>(m_cfg.unit / m_cfg.vDpi));
    putByte(static_cast<uint8_t>(m_cfg.unit / m_cfg.hDpi));
    putU16(static_cast<uint16_t>(m_cfg.unit));"""
new_u = """    // ESC ( U 05 00 [uA, uV, uH, unitLo, unitHi]（unit 恒 2880）
    putByte(0x1B); putByte(0x28); putByte(0x55); putByte(0x05); putByte(0x00);
    putByte(static_cast<uint8_t>(m_cfg.uA));
    putByte(static_cast<uint8_t>(m_cfg.uV));
    putByte(static_cast<uint8_t>(m_cfg.uH));
    putU16(static_cast<uint16_t>(2880));"""
assert old_u in t2
t2 = t2.replace(old_u, new_u)
# ESC ( K
old_k = """    static const uint8_t kCmd[7] = {0x1B, 0x28, 0x4B, 0x02, 0x00, 0x00, 0x02};
    put(kCmd, 7);"""
new_k = """    putByte(0x1B); putByte(0x28); putByte(0x4B); putByte(0x02); putByte(0x00);
    putByte(0x00); putByte(static_cast<uint8_t>(m_cfg.colorMode & 0xFF));"""
assert old_k in t2
t2 = t2.replace(old_k, new_k)
# ESC ( e
old_e = """    static const uint8_t eCmd[7] = {0x1B, 0x28, 0x65, 0x02, 0x00, 0x00, 0x34};
    put(eCmd, 7);"""
new_e = """    putByte(0x1B); putByte(0x28); putByte(0x65); putByte(0x02); putByte(0x00);
    putByte(0x00); putByte(m_cfg.dotSize);"""
assert old_e in t2
t2 = t2.replace(old_e, new_e)
# ESC ( c
old_c = """    putU32(static_cast<uint32_t>(-1227));   // 0xFFFFFB35
    putU32(6896);                            // 0x00001AF0"""
new_c = """    putU32(static_cast<uint32_t>(static_cast<int32_t>(m_cfg.pageFormatTop)));
    putU32(static_cast<uint32_t>(static_cast<int32_t>(m_cfg.pageFormatBottom)));"""
assert old_c in t2
t2 = t2.replace(old_c, new_c)
# ESC ( S
old_s = """    putU32(static_cast<uint32_t>(m_cfg.paperWidth));
    putU32(static_cast<uint32_t>(m_cfg.paperHeight));"""
new_s = """    putU32(static_cast<uint32_t>(m_cfg.paperWidth));
    putU32(static_cast<uint32_t>(static_cast<int32_t>(m_cfg.paperHeight) >= 0
                                     ? m_cfg.paperHeight
                                     : static_cast<int32_t>(m_cfg.paperHeight)));"""
assert old_s in t2
t2 = t2.replace(old_s, new_s)
# ESC ( $ param rule
old_d = """        putU32(static_cast<uint32_t>((m_blockIndex / 16) % 4));"""
new_d = """        putU32(static_cast<uint32_t>(m_cfg.dollarMode == 0
                                         ? 0
                                         : (m_blockIndex / 16) % 4));"""
assert old_d in t2
t2 = t2.replace(old_d, new_d)
open(c, "w", encoding="utf-8", newline="").write(t2)
print("cpp patched")
