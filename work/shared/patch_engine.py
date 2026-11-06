# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace('#include <QDir>', '#include <QCoreApplication>\n#include <QDir>\n#include <QHash>')
old = """    QVector<QVector<uint8_t>> blockRows(cols.size());
    QVector<uint8_t> zerosRow(bpl, 0);
    for (int k = 0; k < blocks; ++k) {
        for (auto &r : blockRows) r.resize(0);
        for (int r = 0; r < mode.blockRows; ++r) {"""
new = """    QVector<QByteArray> blockRows(cols.size());
    for (int k = 0; k < blocks; ++k) {
        for (auto &r : blockRows) r.clear();
        for (int r = 0; r < mode.blockRows; ++r) {"""
assert old in t
t = t.replace(old, new)
old2 = """            for (int c = 0; c < cols.size(); ++c) {
                QVector<uint8_t> packed = pack2BitRows(
                    imgRow >= 0 && planeIndexForColor[c] >= 0
                        ? result.planes.at(planeIndexForColor[c]).data.mid(
                              static_cast<qsizetype>(imgRow) * result.width, result.width)
                        : QVector<uint8_t>(result.width, 0),
                    result.width, 1, nullptr, 0);
                // 行对齐到 bpl
                packed.resize(bpl);
                blockRows[c].append(packed);
            }"""
new2 = """            for (int c = 0; c < cols.size(); ++c) {
                QByteArray packed(bpl, '\\0');
                if (imgRow >= 0 && planeIndexForColor[c] >= 0) {
                    const DevicePlane &dp = result.planes.at(planeIndexForColor[c]);
                    const uint8_t *row = dp.data.constData() +
                                         static_cast<qsizetype>(imgRow) * result.width;
                    uint8_t *dst = reinterpret_cast<uint8_t *>(packed.data());
                    for (int x = 0; x < result.width; ++x)
                        dst[x >> 2] |= static_cast<uint8_t>(
                            (row[x] & 0x03) << (6 - 2 * (x & 3)));
                }
                blockRows[c].append(packed);
            }"""
assert old2 in t
t = t.replace(old2, new2)
open(p, "w", encoding="utf-8", newline="").write(t)
print("patched")
