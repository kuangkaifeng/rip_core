#include "core/encode/plane_pack.h"

namespace mtr {

QVector<uint8_t> pack2BitRows(const QVector<uint8_t> &plane, int width, int height,
                              int *bytesPerLine, int alignBytes)
{
    int bpl = (width + 3) / 4;
    if (alignBytes > 1)
        bpl = ((bpl + alignBytes - 1) / alignBytes) * alignBytes;
    if (bytesPerLine) *bytesPerLine = bpl;

    QVector<uint8_t> out(bpl * height, 0);
    for (int y = 0; y < height; ++y) {
        const uint8_t *src = plane.constData() + static_cast<qsizetype>(y) * width;
        uint8_t *dst = out.data() + static_cast<qsizetype>(y) * bpl;
        for (int x = 0; x < width; ++x) {
            const uint8_t v = src[x] & 0x03;
            const int byteIdx = x >> 2;
            const int bitPos = 6 - 2 * (x & 3);
            dst[byteIdx] |= static_cast<uint8_t>(v << bitPos);
        }
    }
    return out;
}

QVector<uint8_t> pack1BitRows(const QVector<uint8_t> &plane, int width, int height,
                              int *bytesPerLine, int alignBytes)
{
    int bpl = (width + 7) / 8;
    if (alignBytes > 1)
        bpl = ((bpl + alignBytes - 1) / alignBytes) * alignBytes;
    if (bytesPerLine) *bytesPerLine = bpl;

    QVector<uint8_t> out(bpl * height, 0);
    for (int y = 0; y < height; ++y) {
        const uint8_t *src = plane.constData() + static_cast<qsizetype>(y) * width;
        uint8_t *dst = out.data() + static_cast<qsizetype>(y) * bpl;
        for (int x = 0; x < width; ++x) {
            if (src[x] & 0x01) {
                const int byteIdx = x >> 3;
                const int bitPos = 7 - (x & 7);
                dst[byteIdx] |= static_cast<uint8_t>(1u << bitPos);
            }
        }
    }
    return out;
}

} // namespace mtr
