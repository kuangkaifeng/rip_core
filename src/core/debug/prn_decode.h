// ============================================================================
// prn_decode.h —— PRN 解码/验证（ESC/P2 与 HSSF）
// 用于把生成的 prn 解回每块每色点阵，导出预览图，和蒙泰参考 PRN 做比对。
// ============================================================================
#pragma once

#include <QByteArray>
#include <QString>
#include <QVector>
#include <cstdint>

namespace mtr {

struct PrnBlockInfo {
    int blockIndex = 0;
    int colorCode = 0;
    int bytesPerLine = 0;
    int rows = 0;
    int compress = 0;
    int bitDepth = 2;
    uint32_t escDollarParam = 0;
};

struct PrnImage {
    int width = 0;
    int height = 0;
    int blocks = 0;
    QVector<PrnBlockInfo> records;
    // 每块每色的原始解码数据（已解压，2bit 打包）
    QVector<QVector<QByteArray>> blockData;
    // 颜色顺序（第一块出现的顺序）
    QVector<int> colorOrder;
};

class PrnDecoder {
public:
    // 解析 ESC/P2 PRN；失败返回 false 并给出 err
    static bool decodeEscp2(const QString &prnPath, PrnImage *image, QString *err);

    // 导出预览：把各色块拼成一页 24bit BMP（每色一个文件，或合并）
    static bool decodeToDir(const QString &prnPath, const QString &outDir, QString *err);
};

} // namespace mtr
