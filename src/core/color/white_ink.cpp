#include "core/color/white_ink.h"

#include <algorithm>
#include <vector>

namespace mtr {

namespace {

// 二值形态学：膨胀/腐蚀（方形/十字，按 dots 近似到像素）
QVector<uint8_t> morphBinary(const QVector<uint8_t> &mask, int w, int h,
                             int dl, int dt, int dr, int db, bool dilate)
{
    QVector<uint8_t> out(mask.size(), 0);
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            bool hit = false;
            if (dilate) {
                // 只要邻域内有前景就置 1
                const int x0 = std::max(0, x - dl), x1 = std::min(w - 1, x + dr);
                const int y0 = std::max(0, y - dt), y1 = std::min(h - 1, y + db);
                for (int yy = y0; yy <= y1 && !hit; ++yy)
                    for (int xx = x0; xx <= x1; ++xx)
                        if (mask[yy * w + xx]) { hit = true; break; }
            } else {
                // 邻域内只要有背景就置 0（腐蚀）
                const int x0 = std::max(0, x - dl), x1 = std::min(w - 1, x + dr);
                const int y0 = std::max(0, y - dt), y1 = std::min(h - 1, y + db);
                hit = true;
                for (int yy = y0; yy <= y1 && hit; ++yy)
                    for (int xx = x0; xx <= x1; ++xx)
                        if (!mask[yy * w + xx]) { hit = false; break; }
            }
            out[y * w + x] = hit ? 1 : 0;
        }
    }
    return out;
}

} // namespace

QVector<uint8_t> generateWhiteInk(const QVector<uint8_t> &cmyk, int width, int height,
                                  const WhiteInkParams &p)
{
    QVector<uint8_t> white(width * height, 0);
    if (!p.enabled)
        return white;

    // 1) 构造"有彩墨"掩膜：任一通道 > 0
    QVector<uint8_t> colored(width * height, 0);
    for (int i = 0; i < width * height; ++i) {
        const uint8_t *px = cmyk.constData() + i * 4;
        colored[i] = (px[0] | px[1] | px[2] | px[3]) ? 1 : 0;
    }

    // 2) 形态学：invaginate = 内缩（腐蚀）/ expand = 外扩（膨胀）
    const int dl = p.dots[0], dt = p.dots[1], dr = p.dots[2], db = p.dots[3];
    QVector<uint8_t> mask = colored;
    const bool dilate = (p.morphology == QLatin1String("expand"));
    if (dl || dt || dr || db)
        mask = morphBinary(colored, width, height, dl, dt, dr, db, dilate);

    // 3) 输出白墨覆盖度
    const int density = static_cast<int>(std::clamp(p.density, 0.0, 100.0) * 255 / 100);
    for (int i = 0; i < width * height; ++i) {
        if (p.mode == QLatin1String("full"))
            white[i] = static_cast<uint8_t>(density);
        else // color：只在彩色区域（或形态学处理后）铺白
            white[i] = mask[i] ? static_cast<uint8_t>(density) : 0;
    }
    return white;
}

} // namespace mtr
