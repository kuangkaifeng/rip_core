#include "core/color/ink_limit.h"

#include <algorithm>

namespace mtr {

void applyInkLimit(QVector<uint8_t> *cmyk, int pixelCount, const InkLimitConfig &cfg)
{
    if (!cmyk || cmyk->size() < pixelCount * 4)
        return;

    // 单通道上限
    for (int c = 0; c < 4; ++c) {
        const int cap = static_cast<int>(cfg.channelLimit[c] * 255 / 100);
        if (cap >= 255) continue;
        uint8_t *p = cmyk->data() + c;
        for (int i = 0; i < pixelCount; ++i, p += 4)
            *p = static_cast<uint8_t>(std::min<int>(*p, cap));
    }

    // 总墨量上限（简单等比缩放；T3 确认蒙泰具体算法后再精修）
    const int totalLimit = static_cast<int>(cfg.cmykTotalLimit * 255 / 100);
    if (totalLimit <= 0 || totalLimit >= 4 * 255)
        return;
    uint8_t *p = cmyk->data();
    for (int i = 0; i < pixelCount; ++i, p += 4) {
        const int sum = p[0] + p[1] + p[2] + p[3];
        if (sum > totalLimit && sum > 0) {
            for (int c = 0; c < 4; ++c)
                p[c] = static_cast<uint8_t>(p[c] * totalLimit / sum);
        }
    }
}

} // namespace mtr
