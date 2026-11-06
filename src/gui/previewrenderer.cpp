// ============================================================================
// previewrenderer.cpp —— PRN 打印点阵预览渲染（GUI 用）
//
// 设计要点（避免大图卡顿）：
//   * 解码在后台线程执行（调用方 QThread）；
//   * 合成/单通道图像**按目标分辨率采样生成**（不再生成全尺寸 QImage），
//     大图（如 4320×4320）也能在几十毫秒内出图；
//   * 解码前先用 PrnReconstructor::parse 探测内容尺寸，超过内存/时间阈值直接
//     返回错误提示，避免超大 PRN 把内存打爆。
// ============================================================================
#include "gui/previewrenderer.h"

#include <QColor>
#include <QFile>
#include <cstring>

#include "core/decode/prn_reconstruct.h"

namespace mtr {
namespace gui {

namespace {

// 预览所允许的最大内容像素数（约 40M 像素 ≈ 4 平面 160MB）
const qint64 kMaxPreviewPixels = 40ll * 1000ll * 1000ll;

struct Rgb { int r, g, b; };

Rgb inkColor(const QString &ink)
{
    if (ink == QLatin1String("C")) return {0, 170, 220};
    if (ink == QLatin1String("M")) return {220, 0, 130};
    if (ink == QLatin1String("Y")) return {235, 210, 0};
    if (ink == QLatin1String("K")) return {0, 0, 0};
    if (ink == QLatin1String("W1")) return {200, 200, 200};
    if (ink == QLatin1String("W2")) return {160, 160, 160};
    return {128, 128, 128};
}

QString codeToInk(int code, int planes)
{
    if (planes <= 4) {
        switch (code) {
        case 0x04: return QStringLiteral("K");
        case 0x00: return QStringLiteral("C");
        case 0x12: return QStringLiteral("M");
        case 0x11: return QStringLiteral("Y");
        default: return QString();
        }
    }
    switch (code) {
    case 0x00: return QStringLiteral("K");
    case 0x02: return QStringLiteral("C");
    case 0x01: return QStringLiteral("M");
    case 0x04: return QStringLiteral("Y");
    case 0x11: return QStringLiteral("W1");
    case 0x12: return QStringLiteral("W2");
    default: return QString();
    }
}

// 目标显示尺寸（保持宽高比，最长边 maxSide）
QSize fitSize(int w, int h, int maxSide)
{
    if (w <= 0 || h <= 0) return QSize(1, 1);
    if (w <= maxSide && h <= maxSide) return QSize(w, h);
    if (w >= h) return QSize(maxSide, qMax(1, h * maxSide / w));
    return QSize(qMax(1, w * maxSide / h), maxSide);
}

const QVector<uint8_t> &planeOf(const QMap<QString, QVector<uint8_t>> &m, const QString &name)
{
    static const QVector<uint8_t> kEmpty;
    auto it = m.constFind(name);
    return it == m.constEnd() ? kEmpty : it.value();
}

// ---- HSSF 0x5555 解码（先读头判断大小再读全量，避免超大文件一次性读入）----
bool decodeHssf(const QString &prnPath, QMap<QString, QVector<uint8_t>> *planes,
                int *w, int *h, QString *err)
{
    QFile f(prnPath);
    if (!f.open(QIODevice::ReadOnly)) {
        if (err) *err = QStringLiteral("HSSF: 无法打开文件");
        return false;
    }
    const QByteArray hdr = f.read(48);
    if (hdr.size() < 48) {
        if (err) *err = QStringLiteral("HSSF: 文件过短");
        return false;
    }
    auto u32 = [&](int off) -> uint32_t {
        return static_cast<uint32_t>(static_cast<unsigned char>(hdr[off])) |
               (static_cast<uint32_t>(static_cast<unsigned char>(hdr[off + 1])) << 8) |
               (static_cast<uint32_t>(static_cast<unsigned char>(hdr[off + 2])) << 16) |
               (static_cast<uint32_t>(static_cast<unsigned char>(hdr[off + 3])) << 24);
    };
    const uint32_t sig = u32(0);
    const int bpl = static_cast<int>(u32(12));
    const int height = static_cast<int>(u32(16));
    const int width = static_cast<int>(u32(20));
    const int planeCount = static_cast<int>(u32(28));
    if (sig != 0x5555 || width <= 0 || height <= 0 || planeCount <= 0 || bpl <= 0) {
        if (err) *err = QStringLiteral("HSSF: 头部非法");
        return false;
    }
    if (static_cast<qint64>(width) * height > kMaxPreviewPixels) {
        if (err) *err = QStringLiteral("图像过大（%1×%2），已跳过预览").arg(width).arg(height);
        return false;
    }
    const qint64 need = 48 + static_cast<qint64>(height) * planeCount * bpl;
    if (f.size() < need) {
        if (err) *err = QStringLiteral("HSSF: 数据被截断");
        return false;
    }
    f.seek(0);
    const QByteArray data = f.readAll();
    f.close();

    static const char *names[8] = {"K", "C", "M", "Y", "W1", "W2", "S1", "S2"};
    const qsizetype pageSize = static_cast<qsizetype>(width) * height;
    for (int p = 0; p < planeCount; ++p) {
        QVector<uint8_t> plane(pageSize, 0);
        for (int y = 0; y < height; ++y) {
            const char *row = data.constData() + 48 +
                              (static_cast<qint64>(y) * planeCount + p) * bpl;
            for (int x = 0; x < width; ++x) {
                const unsigned char byte = static_cast<unsigned char>(row[x >> 2]);
                plane[static_cast<qsizetype>(y) * width + x] =
                    static_cast<uint8_t>((byte >> (6 - 2 * (x & 3))) & 0x03);
            }
        }
        planes->insert(QString::fromLatin1(p < 8 ? names[p] : "X"), plane);
    }
    *w = width;
    *h = height;
    return true;
}

} // namespace

QImage renderChannel(const QVector<uint8_t> &levels, int w, int h, const QString &ink)
{
    return renderChannelScaled(levels, w, h, ink, 1600);
}

QImage renderChannelScaled(const QVector<uint8_t> &levels, int w, int h,
                           const QString &ink, int maxSide)
{
    const QSize sz = fitSize(w, h, maxSide);
    QImage img(sz, QImage::Format_RGB888);
    if (levels.isEmpty() || w <= 0 || h <= 0) {
        img.fill(Qt::white);
        return img;
    }
    const Rgb c = inkColor(ink);
    for (int oy = 0; oy < sz.height(); ++oy) {
        uint8_t *line = img.scanLine(oy);
        const int sy = static_cast<int>(static_cast<qint64>(oy) * h / sz.height());
        const uint8_t *src = levels.constData() + static_cast<qsizetype>(sy) * w;
        for (int ox = 0; ox < sz.width(); ++ox) {
            const int sx = static_cast<int>(static_cast<qint64>(ox) * w / sz.width());
            const int lvl = src[sx] & 3;
            const double cover = lvl / 3.0;
            line[ox * 3 + 0] = static_cast<uint8_t>(255 - (255 - c.r) * cover);
            line[ox * 3 + 1] = static_cast<uint8_t>(255 - (255 - c.g) * cover);
            line[ox * 3 + 2] = static_cast<uint8_t>(255 - (255 - c.b) * cover);
        }
    }
    return img;
}

QImage composeInks(const QMap<QString, QVector<uint8_t>> &planes, int w, int h)
{
    return composeInksScaled(planes, w, h, 1600);
}

QImage composeInksScaled(const QMap<QString, QVector<uint8_t>> &planes, int w, int h,
                         int maxSide)
{
    const QSize sz = fitSize(w, h, maxSide);
    QImage img(sz, QImage::Format_RGB888);
    if (w <= 0 || h <= 0) {
        img.fill(Qt::white);
        return img;
    }
    const QVector<uint8_t> &C = planeOf(planes, QStringLiteral("C"));
    const QVector<uint8_t> &M = planeOf(planes, QStringLiteral("M"));
    const QVector<uint8_t> &Y = planeOf(planes, QStringLiteral("Y"));
    const QVector<uint8_t> &K = planeOf(planes, QStringLiteral("K"));
    for (int oy = 0; oy < sz.height(); ++oy) {
        uint8_t *line = img.scanLine(oy);
        const int sy = static_cast<int>(static_cast<qint64>(oy) * h / sz.height());
        for (int ox = 0; ox < sz.width(); ++ox) {
            const int sx = static_cast<int>(static_cast<qint64>(ox) * w / sz.width());
            const qsizetype i = static_cast<qsizetype>(sy) * w + sx;
            const double c = C.isEmpty() ? 0.0 : C[i] / 3.0;
            const double m = M.isEmpty() ? 0.0 : M[i] / 3.0;
            const double yy = Y.isEmpty() ? 0.0 : Y[i] / 3.0;
            const double k = K.isEmpty() ? 0.0 : K[i] / 3.0;
            line[ox * 3 + 0] = static_cast<uint8_t>(255.0 * (1 - c) * (1 - k));
            line[ox * 3 + 1] = static_cast<uint8_t>(255.0 * (1 - m) * (1 - k));
            line[ox * 3 + 2] = static_cast<uint8_t>(255.0 * (1 - yy) * (1 - k));
        }
    }
    return img;
}

bool renderPrnPreview(const QString &prnPath, const QImage &original,
                      PreviewData *out, QString *err, int modeIdOverride, int maxSide)
{
    if (!out) return false;
    QFile f(prnPath);
    if (!f.open(QIODevice::ReadOnly)) {
        if (err) *err = QStringLiteral("无法打开 PRN: %1").arg(prnPath);
        return false;
    }
    const QByteArray head = f.peek(8);
    f.close();

    QMap<QString, QVector<uint8_t>> planes;
    int w = 0, h = 0;
    QString fmt;
    QString warn;

    if (head.startsWith(QByteArray("\x00\x00\x00\x1B", 4))) {
        // ---- ESC/P2 ----
        fmt = QStringLiteral("ESC/P2");
        mtr::Escp2JobInfo probe;
        QString perr;
        if (!mtr::PrnReconstructor::parse(prnPath, &probe, &perr)) {
            if (err) *err = QStringLiteral("ESC/P2 结构解析失败: %1").arg(perr);
            return false;
        }
        int probeW = probe.contentWidthDots;
        int probeH = probe.contentHeightDots;
        if (probeW <= 0 && probe.paperWidth > 0) probeW = static_cast<int>(probe.paperWidth);
        if (probeH <= 0) probeH = static_cast<int>(probe.paperHeight) + probe.pageMargin;
        if (probeW > 0 && probeH > 0 &&
            static_cast<qint64>(probeW) * probeH > kMaxPreviewPixels) {
            if (err) *err = QStringLiteral("图像过大（%1×%2），已跳过预览（PRN 本身已生成成功）")
                                .arg(probeW)
                                .arg(probeH);
            return false;
        }
        mtr::PrnPageRaster page;
        mtr::Escp2JobInfo info;
        QString derr;
        if (!mtr::PrnReconstructor::decode(prnPath, &page, &info, &derr, modeIdOverride)) {
            if (err) *err = QStringLiteral("ESC/P2 反解失败: %1").arg(derr);
            return false;
        }
        const int planesCount = info.planes > 0 ? info.planes : int(page.colors.size());
        int top = info.p0;
        if (top <= 0) top = 640;
        int contentW = info.contentWidthDots;
        int contentH = info.contentHeightDots;
        if (contentW <= 0 && info.paperWidth > 0)
            contentW = static_cast<int>(info.paperWidth);
        if (contentH <= 0)
            contentH = static_cast<int>(info.paperHeight) + info.pageMargin;
        if (contentW <= 0 || contentH <= 0) {
            contentW = page.widthDots;
            contentH = page.rows - top;
        }
        if (contentW <= 0 || contentH <= 0) {
            if (err) *err = QStringLiteral("ESC/P2 内容尺寸解析失败");
            return false;
        }
        for (auto it = page.planes.constBegin(); it != page.planes.constEnd(); ++it) {
            const QString ink = codeToInk(it.key(), planesCount);
            if (ink.isEmpty()) continue;
            QVector<uint8_t> cropped(static_cast<qsizetype>(contentW) * contentH, 0);
            for (int y = 0; y < contentH; ++y) {
                const int srcY = y + top;
                if (srcY < 0 || srcY >= page.rows) continue;
                const uint8_t *src = it.value().constData() +
                                     static_cast<qsizetype>(srcY) * page.widthDots;
                uint8_t *dst = cropped.data() + static_cast<qsizetype>(y) * contentW;
                const int n = qMin(contentW, page.widthDots);
                for (int x = 0; x < n; ++x) dst[x] = src[x];
            }
            planes.insert(ink, cropped);
        }
        w = contentW;
        h = contentH;
        page = mtr::PrnPageRaster();  // 尽早释放页面 raster
    } else if (head.startsWith(QByteArray("\x55\x55", 2))) {
        fmt = QStringLiteral("HSSF");
        if (!decodeHssf(prnPath, &planes, &w, &h, err))
            return false;
    } else {
        if (err) *err = QStringLiteral("未知 PRN 格式（头: %1）")
                            .arg(QString::fromLatin1(head.toHex(' ')));
        return false;
    }

    out->ok = true;
    out->format = fmt;
    out->widthDots = w;
    out->heightDots = h;

    // 直接按显示分辨率渲染（大图不卡）
    for (auto it = planes.constBegin(); it != planes.constEnd(); ++it) {
        out->channels.insert(it.key(),
                             renderChannelScaled(it.value(), w, h, it.key(), maxSide));
    }
    out->composite = composeInksScaled(planes, w, h, maxSide);

    if (!original.isNull()) {
        QImage o = original.convertToFormat(QImage::Format_RGB888);
        o = o.scaled(fitSize(o.width(), o.height(), maxSide), Qt::KeepAspectRatio,
                     Qt::SmoothTransformation);
        out->original = o;
    }
    out->note = warn;
    return true;
}

} // namespace gui
} // namespace mtr
