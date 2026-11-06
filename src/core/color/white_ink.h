// ============================================================================
// white_ink.h —— 白墨/专色生成
// 语义对应蒙泰: inputColorEditor{mode:full|color} + inkIE{mode:invaginate|expand,
// dots:[4], index:4} + margin。
// 输出为逐像素 0..255 的白墨覆盖度（后续和彩墨一起加网/生成通道）。
// ============================================================================
#pragma once

#include <QVector>
#include <cstdint>
#include "core/job_config.h"

namespace mtr {

struct WhiteInkParams {
    bool enabled = false;
    QString mode = QStringLiteral("full");  // full | color
    QString morphology = QStringLiteral("invaginate"); // invaginate | expand
    int dots[4] = {0, 0, 0, 0};             // 左/上/右/下
    double density = 100.0;                 // 0..100
    int inkIndex = 4;
};

// cmyk: 交错 4 通道（分色结果），width/height。返回逐像素白墨覆盖度（0..255）。
QVector<uint8_t> generateWhiteInk(const QVector<uint8_t> &cmyk, int width, int height,
                                  const WhiteInkParams &p);

} // namespace mtr
