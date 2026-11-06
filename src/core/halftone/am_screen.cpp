#include "core/halftone/am_screen.h"

#include <cmath>
#include <algorithm>

namespace mtr {

namespace {

constexpr double kPi = 3.14159265358979323846;

// 简单阈值矩阵（8x8 Bayer），配合角度/频率做 AM 近似。
// TODO(T2/T3): 蒙泰 ScreenProcess 的真实网点函数（形状/角度/频率/2bit 4 级划分）
//             待 docs/prn_escp2.md / color_pipeline.md 定稿后替换。
const int kBayer8[8][8] = {
    {0, 32, 8, 40, 2, 34, 10, 42},
    {48, 16, 56, 24, 50, 18, 58, 26},
    {12, 44, 4, 36, 14, 46, 6, 38},
    {60, 28, 52, 20, 62, 30, 54, 22},
    {3, 35, 11, 43, 1, 33, 9, 41},
    {51, 19, 59, 27, 49, 17, 57, 25},
    {15, 47, 7, 39, 13, 45, 5, 37},
    {63, 31, 55, 23, 61, 29, 53, 21},
};

} // namespace

QVector<uint8_t> AmScreen::screen(const QVector<uint8_t> &gray, int width, int height) const
{
    QVector<uint8_t> out(gray.size(), 0);
    const int levels = std::max(2, m_cfg.levels);
    const double cells = std::max(1.0, static_cast<double>(m_cfg.xDPI) /
                                           std::max(1, m_cfg.frequencyLPI));
    const int cell = std::max(1, static_cast<int>(std::lround(cells)));
    const double rad = m_cfg.angleDeg * kPi / 180.0;
    const double ca = std::cos(rad), sa = std::sin(rad);

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const double u = x * ca + y * sa;
            const double v = -x * sa + y * ca;
            const int uu = static_cast<int>(std::floor(u)) % cell;
            const int vv = static_cast<int>(std::floor(v)) % cell;
            const int t = kBayer8[(vv * 8 / std::max(1, cell)) & 7]
                                [(uu * 8 / std::max(1, cell)) & 7];
            const int threshold = t * 255 / 64;
            const int val = gray[y * width + x];
            int dot = 0;
            for (int lv = 1; lv < levels; ++lv) {
                if (val * (levels - 1) / 255 >= lv &&
                    val >= threshold / (levels - 1) * (levels - lv))
                    dot = lv;
            }
            out[y * width + x] = static_cast<uint8_t>(std::min(dot, levels - 1));
        }
    }
    return out;
}

} // namespace mtr
