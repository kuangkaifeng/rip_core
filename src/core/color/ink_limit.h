// ============================================================================
// ink_limit.h —— 总墨量限制
// 输入/输出：CMYK 逐像素，0..255 表示墨量。
// 规则目标与蒙泰 inkLimit 一致（T3 定阈值语义：逐通道 cap 或总量 cap）。
// ============================================================================
#pragma once

#include <QVector>
#include <cstdint>

namespace mtr {

struct InkLimitConfig {
    int cmykTotalLimit = 400;   // 百分比，400 = 不限制
    int channelLimit[4] = {100, 100, 100, 100}; // 单通道上限 %
};

// iccCmyk: 交错 4 通道
void applyInkLimit(QVector<uint8_t> *cmyk, int pixelCount, const InkLimitConfig &cfg);

} // namespace mtr
