# -*- coding: utf-8 -*-
# 1) image_io.h 增加 resolveImageDpi
p = r"D:\work\RIP核心分析\src\core\image_io.h"
t = open(p, encoding="utf-8").read()
if "resolveImageDpi" not in t:
    t = t.replace("bool loadRgba(const QString &path, QImage *out, QString *err);",
"""bool loadRgba(const QString &path, QImage *out, QString *err);

// 按蒙泰实测语义解析输入图像 DPI：
//   PNG：pHYs（unit=1）-> dpi；无 pHYs -> 72
//   JPEG：JFIF unit=1 -> xdensity；unit=2 -> xdensity*2.54；unit=0/无 JFIF -> 72
//   其它：Qt dpm>0 -> dpi；否则 72
// （oracle 实测：860x564 无有效 DPI 的 JPEG 按 72dpi 处理 -> 内容 8600x5640）
int resolveImageDpi(const QString &path, const QImage &img);""")
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("image_io.h updated")

# 2) image_io.cpp 实现
p = r"D:\work\RIP核心分析\src\core\image_io.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace('#include <QImageReader>\n#include <QFileInfo>',
              '#include <QImageReader>\n#include <QFileInfo>\n#include <QFile>\n#include <cmath>')
impl = '''
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
            const int jfif = head.indexOf(QByteArray("JFIF\\0", 5));
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

'''
t = t.replace("bool saveBmp(const QImage &img, const QString &path, QString *err)", impl + "bool saveBmp(const QImage &img, const QString &path, QString *err)")
open(p, "w", encoding="utf-8", newline="").write(t)
print("image_io.cpp updated")

# 3) rip_engine 使用 resolveImageDpi
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace("    const int dpi = imageDpi(image);",
              "    const int dpi = image::resolveImageDpi(job.inputPath, image);")
open(p, "w", encoding="utf-8", newline="").write(t)
print("rip_engine uses resolveImageDpi")
