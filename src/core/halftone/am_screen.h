// ============================================================================
// am_screen.h —— AM/FM 调幅/调频加网（输出 2bit 点大小 0..3）
// 蒙泰的加网由 ScreenProcess 模块完成；我们要复刻其网点形状/角度/频率/灰阶
// 与 2bit 量化的对应关系（T3/T2 给出参数来源）。
// ============================================================================
#pragma once

#include <QVector>
#include <cstdint>

namespace mtr {

enum class ScreenType {
    AM = 0,          // 调幅（网点大小变化）
    FM = 1,          // 调频（随机/误差扩散类）
    AM_FM = 2,       // 混合
    AM_CIRCLE = 3,
    AM_SQUARE = 4,
    AM_ELLIPSE = 5,
    AM_DIAMOND = 6,
    AM_LINE = 7
};

struct ScreenConfig {
    ScreenType type = ScreenType::AM;
    int frequencyLPI = 60;       // AM 网点频率
    double angleDeg = 0.0;       // 加网角度（每色通常不同，防龟纹）
    int levels = 4;              // 2bit = 4 级（0..3）
    int xDPI = 720;
    int yDPI = 720;
};

// 单通道连续调（0..255）→ 点大小（0..3）
class AmScreen {
public:
    void configure(const ScreenConfig &cfg) { m_cfg = cfg; }
    QVector<uint8_t> screen(const QVector<uint8_t> &gray, int width, int height) const;
    const ScreenConfig &config() const { return m_cfg; }

private:
    ScreenConfig m_cfg;
};

} // namespace mtr
