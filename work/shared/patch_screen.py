# -*- coding: utf-8 -*-
import os
# 1) fix converter output section
p = r"D:\work\RIP核心分析\work\shared\build_screen_data.py"
t = open(p, encoding="utf-8").read()
old = """    data = bytearray(size * size * 3)
    for i in range(size * size):
        f = field[ci][i]
        if f is None:
            f = (1, 86, 171)  # 未覆盖像素兜底（理论上不应出现）
        data[i*3+0] = min(f[0], 255)
        data[i*3+1] = min(f[1], 255)
        data[i*3+2] = min(f[2], 255)"""
new = """    data = bytearray(size * size * 3)
    for i in range(size * size):
        t1 = field[0][i] if field[0][i] is not None else 1
        t2 = field[1][i] if field[1][i] is not None else 86
        t3 = field[2][i] if field[2][i] is not None else 171
        data[i*3+0] = min(t1, 255)
        data[i*3+1] = min(t2, 255)
        data[i*3+2] = min(t3, 255)"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)

# 2) screen.h: threshold -> 3 bytes per pixel
h = r"D:\work\RIP核心分析\src\core\halftone\screen.h"
t2 = open(h, encoding="utf-8").read()
old2 = """    int size = 64;
    QVector<uint8_t> threshold;   // size*size"""
new2 = """    int size = 64;
    // 每像素 3 字节阈值 [T1,T2,T3]：level = (v>=T1)+(v>=T2)+(v>=T3)
    QVector<uint8_t> threshold;   // size*size*3"""
assert old2 in t2
t2 = t2.replace(old2, new2)
open(h, "w", encoding="utf-8", newline="").write(t2)

# 3) screen.cpp: adapt
c = r"D:\work\RIP核心分析\src\core\halftone\screen.cpp"
t3 = open(c, encoding="utf-8").read()
# fallback: fill 3 thresholds
old3 = """        ScreenChannel ch;
        ch.size = size;
        ch.threshold.resize(size * size);
        const uint32_t seed = 0x9E3779B9u * (c + 1);
        for (int y = 0; y < size; ++y) {
            for (int x = 0; x < size; ++x) {
                // 交织 hash 产生近似随机（蓝噪声的粗糙替代）
                const uint32_t h = hash32(static_cast<uint32_t>(x) * 0x1F1F1F1Fu ^
                                          static_cast<uint32_t>(y) * 0x85EBCA6Bu ^ seed);
                ch.threshold[y * size + x] = static_cast<uint8_t>(h >> 24);
            }
        }"""
new3 = """        ScreenChannel ch;
        ch.size = size;
        ch.threshold.resize(size * size * 3);
        const uint32_t seed = 0x9E3779B9u * (c + 1);
        for (int y = 0; y < size; ++y) {
            for (int x = 0; x < size; ++x) {
                const uint32_t h = hash32(static_cast<uint32_t>(x) * 0x1F1F1F1Fu ^
                                          static_cast<uint32_t>(y) * 0x85EBCA6Bu ^ seed);
                const int idx = (y * size + x) * 3;
                ch.threshold[idx + 0] = static_cast<uint8_t>((h >> 24) % 86);
                ch.threshold[idx + 1] = static_cast<uint8_t>(86 + ((h >> 16) % 86));
                ch.threshold[idx + 2] = static_cast<uint8_t>(171 + ((h >> 8) % 85));
            }
        }"""
assert old3 in t3
t3 = t3.replace(old3, new3)
# load: size*size*3
old4 = """        ScreenChannel ch;
        ch.size = size;
        ch.threshold.resize(size * size);"""
new4 = """        ScreenChannel ch;
        ch.size = size;
        ch.threshold.resize(size * size * 3);"""
assert old4 in t3
t3 = t3.replace(old4, new4)
old5 = """        if (raw.size() < size * size) {
            if (err) *err = QStringLiteral("threshold file too small: %1").arg(fileName);
            return false;
        }
        memcpy(ch.threshold.data(), raw.constData(), static_cast<size_t>(size * size));"""
new5 = """        if (raw.size() < size * size * 3) {
            if (err) *err = QStringLiteral("threshold file too small: %1").arg(fileName);
            return false;
        }
        memcpy(ch.threshold.data(), raw.constData(), static_cast<size_t>(size * size * 3));"""
assert old5 in t3
t3 = t3.replace(old5, new5)
# dither: use 3 thresholds
old6 = """            const int base3 = 3 * t;              // 0..765
            int lvl = base3 / 255;                // 0..2
            const int fracInt = base3 % 255;      // 0..254
            const int tx = (x + ch.phaseX) % size;
            const int ty = (y + ch.phaseY) % size;
            const int T = ch.threshold[ty * size + tx];
            if (fracInt >= T) ++lvl;
            (*level)[idx] = static_cast<uint8_t>(qMin(lvl, 3));"""
new6 = """            const int tx = (x + ch.phaseX) % size;
            const int ty = (y + ch.phaseY) % size;
            const int ti = (ty * size + tx) * 3;
            const int t1 = ch.threshold[ti + 0];
            const int t2 = ch.threshold[ti + 1];
            const int t3 = ch.threshold[ti + 2];
            int lvl = (t >= t1) + (t >= t2) + (t >= t3);
            (*level)[idx] = static_cast<uint8_t>(qBound(0, lvl, 3));"""
assert old6 in t3
t3 = t3.replace(old6, new6)
open(c, "w", encoding="utf-8", newline="").write(t3)
print("screen class updated to 3-threshold format")
