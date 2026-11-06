#include "core/debug/bmp_writer.h"

#include <QFile>
#include <QTextStream>
#include <cstring>
#include <vector>

namespace mtr {

namespace {
inline void put16(std::vector<uint8_t> &v, uint16_t x)
{
    v.push_back(static_cast<uint8_t>(x & 0xFF));
    v.push_back(static_cast<uint8_t>((x >> 8) & 0xFF));
}
inline void put32(std::vector<uint8_t> &v, uint32_t x)
{
    v.push_back(static_cast<uint8_t>(x & 0xFF));
    v.push_back(static_cast<uint8_t>((x >> 8) & 0xFF));
    v.push_back(static_cast<uint8_t>((x >> 16) & 0xFF));
    v.push_back(static_cast<uint8_t>((x >> 24) & 0xFF));
}
} // namespace

bool writeBmp24(const QImage &image, const QString &path, QString *err)
{
    if (image.isNull()) {
        if (err) *err = QStringLiteral("bmp: null image");
        return false;
    }
    const QImage img = image.format() == QImage::Format_RGB888
                           ? image
                           : image.convertToFormat(QImage::Format_RGB888);
    const int w = img.width();
    const int h = img.height();
    const int rowBytes = ((w * 3) + 3) & ~3;
    const uint32_t pixelDataSize = static_cast<uint32_t>(rowBytes) * static_cast<uint32_t>(h);
    const uint32_t fileSize = 54u + pixelDataSize;

    std::vector<uint8_t> out;
    out.reserve(fileSize);

    // BITMAPFILEHEADER
    out.push_back('B');
    out.push_back('M');
    put32(out, fileSize);
    put32(out, 0);
    put32(out, 54);
    // BITMAPINFOHEADER
    put32(out, 40);
    put32(out, static_cast<uint32_t>(w));
    put32(out, static_cast<uint32_t>(h));
    put16(out, 1);
    put16(out, 24);
    put32(out, 0); // BI_RGB
    put32(out, pixelDataSize);
    put32(out, 2835);
    put32(out, 2835);
    put32(out, 0);
    put32(out, 0);

    for (int y = h - 1; y >= 0; --y) {
        const uint8_t *src = img.constScanLine(y);
        for (int x = 0; x < w; ++x) {
            out.push_back(src[x * 3 + 2]);
            out.push_back(src[x * 3 + 1]);
            out.push_back(src[x * 3 + 0]);
        }
        for (int pad = w * 3; pad < rowBytes; ++pad)
            out.push_back(0);
    }

    QFile f(path);
    if (!f.open(QIODevice::WriteOnly)) {
        if (err) *err = QStringLiteral("bmp: cannot write %1").arg(path);
        return false;
    }
    const qint64 n = f.write(reinterpret_cast<const char *>(out.data()),
                             static_cast<qint64>(out.size()));
    f.close();
    if (n != static_cast<qint64>(out.size())) {
        if (err) *err = QStringLiteral("bmp: short write %1").arg(path);
        return false;
    }
    return true;
}

} // namespace mtr
