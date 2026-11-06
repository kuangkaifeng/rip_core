// ============================================================================
// linearization.h —— 线性化（通道曲线/LUT）
// 蒙泰 prs 内嵌线性化数据；对每个通道做输入值 -> 输出值 的映射。
// ============================================================================
#pragma once

#include <QByteArray>
#include <QVector>
#include <cstdint>

namespace mtr {

class Linearization {
public:
    // 从 prs 提取的原始 LUT 建立 4 通道曲线（每通道可按 256 点表或分段数据）
    bool loadFromPrs(const QByteArray &raw, int channelCount);
    bool isReady() const { return !m_curves.isEmpty(); }

    // 原位修改交错 CMYK(A) 数据
    void apply(QVector<uint8_t> *data, int pixelCount, int channels) const;

private:
    QVector<QVector<uint8_t>> m_curves; // [channel][256]
};

} // namespace mtr
