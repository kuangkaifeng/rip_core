#include "core/color/linearization.h"

namespace mtr {

bool Linearization::loadFromPrs(const QByteArray &raw, int channelCount)
{
    Q_UNUSED(raw);
    Q_UNUSED(channelCount);
    // TODO(T3): .prs 内线性化 LUT 的具体编码待定（docs/prs_format.md）。
    m_curves.clear();
    return false;
}

void Linearization::apply(QVector<uint8_t> *data, int pixelCount, int channels) const
{
    if (!data || m_curves.isEmpty())
        return;
    const int n = qMin(channels, m_curves.size());
    uint8_t *p = data->data();
    for (int i = 0; i < pixelCount; ++i, p += channels) {
        for (int c = 0; c < n; ++c) {
            const QVector<uint8_t> &curve = m_curves[c];
            if (curve.size() == 256)
                p[c] = curve[p[c]];
        }
    }
}

} // namespace mtr
