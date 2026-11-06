#include "core/image_io.h"
#include "core/debug/bmp_writer.h"

#include <QImageReader>
#include <QFileInfo>
#include <QFile>
#include <cmath>

namespace mtr {
namespace image {

bool loadRgba(const QString &path, QImage *out, QString *err)
{
    if (!out) return false;
    if (!QFileInfo::exists(path)) {
        if (err) *err = QStringLiteral("image not found: %1").arg(path);
        return false;
    }
    QImageReader reader(path);
    reader.setAutoTransform(false);
    QImage img = reader.read();
    if (img.isNull()) {
        if (err) *err = QStringLiteral("image load failed (%1): %2")
                            .arg(path, reader.errorString());
        return false;
    }
    // 统一成 RGBA8888
    if (img.format() != QImage::Format_RGBA8888)
        img = img.convertToFormat(QImage::Format_RGBA8888);
    *out = img;
    return true;
}


int resolveImageDpi(const QString &path, const QImage &img)
{
    QFile f(path);
    if (f.open(QIODevice::ReadOnly)) {
        const QByteArray head = f.read(64 * 1024);
        f.close();
        // ---- PNG: pHYs chunk ----
        static const unsigned char pngSig[8] = {0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A};
        if (head.size() > 8 && std::memcmp(head.constData(), pngSig, 8) == 0) {
            int off = 8;
            while (off + 8 <= head.size()) {
                const unsigned char *p = reinterpret_cast<const unsigned char *>(head.constData() + off);
                const quint32 len = (quint32(p[0]) << 24) | (quint32(p[1]) << 16) |
                                    (quint32(p[2]) << 8) | quint32(p[3]);
                const QByteArray type = head.mid(off + 4, 4);
                if (type == "pHYs" && off + 8 + 9 <= head.size()) {
                    const unsigned char *d = p + 8;
                    const quint32 ppuX = (quint32(d[0]) << 24) | (quint32(d[1]) << 16) |
                                         (quint32(d[2]) << 8) | quint32(d[3]);
                    const int unit = d[8];
                    if (unit == 1 && ppuX > 0)
                        return static_cast<int>(std::lround(ppuX * 0.0254));
                    return 72;
                }
                if (len > 0x7FFFFFFF) break;
                off += 8 + static_cast<int>(len) + 4;
            }
            return 72;
        }
        // ---- JPEG: JFIF APP0 ----
        if (head.size() > 4 && static_cast<unsigned char>(head[0]) == 0xFF &&
            static_cast<unsigned char>(head[1]) == 0xD8) {
            const int jfif = head.indexOf(QByteArray("JFIF\0", 5));
            if (jfif >= 0 && jfif + 12 < head.size()) {
                const unsigned char *s = reinterpret_cast<const unsigned char *>(head.constData() + jfif);
                const int units = s[7];
                const int xd = (int(s[8]) << 8) | int(s[9]);
                if (units == 1 && xd > 0) return xd;
                if (units == 2 && xd > 0) return static_cast<int>(std::lround(xd * 2.54));
                return 72;   // units==0：aspect only，蒙泰按 72dpi
            }
            return 72;
        }
    }
    const int dpm = img.dotsPerMeterX();
    if (dpm > 0) return static_cast<int>(std::lround(dpm * 0.0254));
    return 72;
}

bool saveBmp(const QImage &img, const QString &path, QString *err)
{
    return writeBmp24(img, path, err);
}

} // namespace image
} // namespace mtr
