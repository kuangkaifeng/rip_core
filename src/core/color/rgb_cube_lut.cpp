// ============================================================================
// rgb_cube_lut.cpp —— RGB 9×9×9 三维 LUT 加载 + 三线性插值
//
// 数据来源：Lead 从 oracle 的 9³ 立方体探针（probe_rgbcube9_540）反解，
// 见 reference/profiles/rgb_cube9.{bin,json}。T3 会用更多探针独立校验。
// ============================================================================
#include "core/color/rgb_cube_lut.h"

#include <QFile>
#include <QtGlobal>
#include <algorithm>
#include <climits>
#include <cmath>
#include <cstring>

#include "core/resources.h"

namespace mtr {

namespace {

// 非均匀轴网格：0,32,64,96,128,160,192,224,255
const int kGrid[9] = {0, 32, 64, 96, 128, 160, 192, 224, 255};

inline float lerp(float a, float b, float t) { return a + (b - a) * t; }
inline unsigned char clampByte(int v) { return static_cast<unsigned char>(qBound(0, v, 255)); }

} // namespace

const int *RgbCubeLut::grid() { return kGrid; }

QString RgbCubeLut::defaultPath()
{
    const QString dir = resolveResourceDir(QStringLiteral("color"));
    if (dir.isEmpty())
        return QString();
    return dir + QStringLiteral("/rgb_cube9.bin");
}

bool RgbCubeLut::load(const QString &path, QString *err)
{
    m_ready = false;
    if (path.isEmpty()) {
        if (err) *err = QStringLiteral("cube lut: empty path");
        return false;
    }
    QFile f(path);
    if (!f.exists() || !f.open(QIODevice::ReadOnly)) {
        if (err) *err = QStringLiteral("cube lut: cannot open %1").arg(path);
        return false;
    }
    const QByteArray data = f.readAll();
    f.close();
    if (!loadFromData(data, err)) {
        if (err) *err = QStringLiteral("%1 (%2)").arg(*err, path);
        return false;
    }
    return true;
}

bool RgbCubeLut::loadFromData(const QByteArray &data, QString *err)
{
    m_ready = false;
    m_size = 0;
    m_channels = 0;
    m_data.clear();
    if (data.size() < 7 || data.left(4) != QByteArray("RGB9", 4)) {
        if (err) *err = QStringLiteral("cube lut: bad magic");
        return false;
    }
    const int size = static_cast<uint8_t>(data.at(4)) |
                     (static_cast<uint8_t>(data.at(5)) << 8);
    const int channels = static_cast<uint8_t>(data.at(6));
    if (size != kSize || channels != kChannels) {
        if (err) *err = QStringLiteral("cube lut: size=%1 channels=%2 (expect 9/4)")
                            .arg(size).arg(channels);
        return false;
    }
    const int expect = kGridPoints * kChannels;
    if (data.size() - 7 != expect) {
        if (err) *err = QStringLiteral("cube lut: data=%1 expect %2")
                            .arg(data.size() - 7).arg(expect);
        return false;
    }
    m_size = size;
    m_channels = channels;
    m_data = data.mid(7);
    buildAxisTables();
    m_ready = true;
    return true;
}

void RgbCubeLut::buildAxisTables()
{
    for (int v = 0; v < 256; ++v) {
        int i0 = 0;
        float t = 0.0f;
        if (v <= kGrid[0]) {
            i0 = 0;
            t = 0.0f;
        } else if (v >= kGrid[kSize - 1]) {
            i0 = kSize - 2;
            t = 1.0f;
        } else {
            for (int i = 0; i < kSize - 1; ++i) {
                if (v >= kGrid[i] && v <= kGrid[i + 1]) {
                    i0 = i;
                    t = static_cast<float>(v - kGrid[i]) /
                        static_cast<float>(kGrid[i + 1] - kGrid[i]);
                    break;
                }
            }
        }
        m_i0[v] = i0;
        m_i1[v] = i0 + 1;
        m_t[v] = t;
    }
}

void RgbCubeLut::axis(int v, int *i0, int *i1, float *t) const
{
    v = qBound(0, v, 255);
    *i0 = m_i0[v];
    *i1 = m_i1[v];
    *t = m_t[v];
}

bool RgbCubeLut::lookup(int r, int g, int b, unsigned char out[kChannels]) const
{
    if (!m_ready || !out)
        return false;
    int r0, r1, g0, g1, b0, b1;
    float tr, tg, tb;
    axis(r, &r0, &r1, &tr);
    axis(g, &g0, &g1, &tg);
    axis(b, &b0, &b1, &tb);

    const int S = m_size;
    const int plane = kGridPoints;
    const uint8_t *base = reinterpret_cast<const uint8_t *>(m_data.constData());
    // 角点索引（b 变化最快）
    const int i000 = (r0 * S + g0) * S + b0;
    const int i001 = (r0 * S + g0) * S + b1;
    const int i010 = (r0 * S + g1) * S + b0;
    const int i011 = (r0 * S + g1) * S + b1;
    const int i100 = (r1 * S + g0) * S + b0;
    const int i101 = (r1 * S + g0) * S + b1;
    const int i110 = (r1 * S + g1) * S + b0;
    const int i111 = (r1 * S + g1) * S + b1;

    for (int c = 0; c < kChannels; ++c) {
        const uint8_t *p = base + static_cast<qsizetype>(c) * plane;
        const float v000 = p[i000], v001 = p[i001], v010 = p[i010], v011 = p[i011];
        const float v100 = p[i100], v101 = p[i101], v110 = p[i110], v111 = p[i111];
        const float b00 = lerp(v000, v100, tr);
        const float b10 = lerp(v010, v110, tr);
        const float b01 = lerp(v001, v101, tr);
        const float b11 = lerp(v011, v111, tr);
        const float g0v = lerp(b00, b10, tg);
        const float g1v = lerp(b01, b11, tg);
        const float val = lerp(g0v, g1v, tb);
        out[c] = clampByte(static_cast<int>(std::lround(val)));
    }
    return true;
}

bool RgbCubeLut::lookupTetrahedral(int r, int g, int b, unsigned char out[kChannels]) const
{
    if (!m_ready || !out)
        return false;
    int r0, r1, g0, g1, b0, b1;
    float tr, tg, tb;
    axis(r, &r0, &r1, &tr);
    axis(g, &g0, &g1, &tg);
    axis(b, &b0, &b1, &tb);

    const int S = m_size;
    const int plane = kGridPoints;
    const uint8_t *base = reinterpret_cast<const uint8_t *>(m_data.constData());
    const int i000 = (r0 * S + g0) * S + b0;
    const int i001 = (r0 * S + g0) * S + b1;
    const int i010 = (r0 * S + g1) * S + b0;
    const int i011 = (r0 * S + g1) * S + b1;
    const int i100 = (r1 * S + g0) * S + b0;
    const int i101 = (r1 * S + g0) * S + b1;
    const int i110 = (r1 * S + g1) * S + b0;
    const int i111 = (r1 * S + g1) * S + b1;

    for (int c = 0; c < kChannels; ++c) {
        const uint8_t *p = base + static_cast<qsizetype>(c) * plane;
        const float v000 = p[i000], v001 = p[i001], v010 = p[i010], v011 = p[i011];
        const float v100 = p[i100], v101 = p[i101], v110 = p[i110], v111 = p[i111];
        float v = v000;
        if (tr >= tg) {
            if (tg >= tb)                 // r >= g >= b
                v += tr * (v100 - v000) + tg * (v110 - v100) + tb * (v111 - v110);
            else if (tr >= tb)            // r >= b >= g
                v += tr * (v100 - v000) + tb * (v101 - v100) + tg * (v111 - v101);
            else                          // b >= r >= g
                v += tb * (v001 - v000) + tr * (v101 - v001) + tg * (v111 - v101);
        } else {
            if (tb >= tg)                 // b >= g >= r
                v += tb * (v001 - v000) + tg * (v011 - v001) + tr * (v111 - v011);
            else if (tg >= tb)            // g >= b >= r
                v += tg * (v010 - v000) + tb * (v011 - v010) + tr * (v111 - v011);
            else                          // g >= r >= b
                v += tg * (v010 - v000) + tr * (v110 - v010) + tb * (v111 - v110);
        }
        out[c] = clampByte(static_cast<int>(std::lround(v)));
    }
    return true;
}

} // namespace mtr
