// ============================================================================
// rip_engine.cpp —— RIP 主引擎（mtr）
//
// 数据流：
//   QImage(RGBA) --ICC--> CMYK 设备墨量 --screen(FM 2bit)--> 页面点阵 level
//        --布局/编码--> ESC/P2（A3-DTF-1390）或 HSSF 0x5555（H13 板卡机）
//
// 说明：版面布局的 MVP 实现在本文件内（公式见 docs/02_geometry_escp2.md），
// 后续可由 src/core/encode/layout_escp2 替换（engine-dev）。
// ============================================================================
#include "core/rip_engine.h"

#include <QCoreApplication>
#include <QDir>
#include <QHash>
#include <QFile>
#include <QFileInfo>
#include <QImage>
#include <QDebug>
#include <QJsonArray>
#include <cmath>
#include <cstring>
#include <cstdio>

#include "core/image_io.h"
#include "core/resources.h"
#include "core/color/icc_transform.h"
#include "core/color/rgb_cube_lut.h"
#include "core/encode/escp2_writer.h"
#include "core/encode/layout_escp2.h"
#include "core/encode/hssf_writer.h"
#include "core/encode/plane_pack.h"
#include "core/halftone/screen.h"

namespace mtr {

namespace {

// 设备墨水通道语义
enum Ink { INK_C = 0, INK_M, INK_Y, INK_K, INK_W1, INK_W2 };

struct InkPlane {
    int ink = INK_C;
    QVector<uint8_t> ink8;   // 内容点阵尺寸上的墨量 0..255
};

QString inkName(int ink)
{
    switch (ink) {
    case INK_C: return QStringLiteral("C");
    case INK_M: return QStringLiteral("M");
    case INK_Y: return QStringLiteral("Y");
    case INK_K: return QStringLiteral("K");
    case INK_W1: return QStringLiteral("W1");
    default: return QStringLiteral("W2");
    }
}

// ESC/P2 记录颜色码与语义（4-plane / 6-plane，来自 oracle 语料实测）
struct EscColorDef { uint8_t code; int ink; };
QVector<EscColorDef> escColorsForPlanes(int planes)
{
    if (planes <= 4) {
        return {{0x04, INK_K}, {0x00, INK_C}, {0x12, INK_M}, {0x11, INK_Y}};
    }
    // 6-plane（CMYKW1W2）实测记录顺序：W2,W1,K,C,M,Y
    return {{0x12, INK_W2}, {0x11, INK_W1}, {0x00, INK_K},
            {0x02, INK_C}, {0x01, INK_M}, {0x04, INK_Y}};
}

int imageDpi(const QImage &img)
{
    const int dpm = img.dotsPerMeterX();
    // 无内嵌 DPI 时蒙泰按 72dpi 处理（oracle 实测：860x564 无 DPI JPEG -> 内容 8600x5640）
    if (dpm <= 0) return 72;
    return static_cast<int>(std::lround(dpm * 0.0254));
}

// 环境变量开关：非空且非 "0"/"false" 视为真
bool envEnabled(const char *name)
{
    const QByteArray v = qgetenv(name).trimmed();
    if (v.isEmpty()) return false;
    if (v == "0") return false;
    if (v.compare("false", Qt::CaseInsensitive) == 0) return false;
    return true;
}

// 最近邻重采样：从 srcW×srcH 的对齐通道数据 -> dstW×dstH
QVector<uint8_t> resampleNearest(const QVector<uint8_t> &src, int srcW, int srcH,
                                 int dstW, int dstH)
{
    QVector<uint8_t> dst(static_cast<qsizetype>(dstW) * dstH);
    for (int y = 0; y < dstH; ++y) {
        const int sy = static_cast<int>(static_cast<long long>(y) * srcH / dstH);
        for (int x = 0; x < dstW; ++x) {
            const int sx = static_cast<int>(static_cast<long long>(x) * srcW / dstW);
            dst[static_cast<qsizetype>(y) * dstW + x] = src[static_cast<qsizetype>(sy) * srcW + sx];
        }
    }
    return dst;
}

} // namespace

bool RipEngine::buildDevicePlanes(const RipJob &job, const PrsConfig &prs,
                                  const QImage &image, RipResult *result, QString *err)
{
    Q_UNUSED(err);
    const int imgW = image.width();
    const int imgH = image.height();
    const int dpi = image::resolveImageDpi(job.inputPath, image);

    const PrsMode *mode = prs.mode(job.modeId);
    PrsMode def;
    if (!mode) {
        def.modeId = job.modeId;
        def.xDPI = 720;
        def.yDPI = 720;
        def.planes = 4;
        mode = &def;
    }

    // ---- 内容点阵尺寸（打印分辨率下的点阵）----
    // A3-DTF-1390（ESC/P2）：几何以 escp2ModeParams 实测表为准（m5/m7/m9 与 PrsConfig 的 dpi 字符串不同）
    int contentWDots = 0;
    int contentHDots = 0;
    if (prs.version == 3) {
        const Escp2ModeParams mp = escp2ModeParams(job.modeId);
        const int hdpi = qMax(1, mp.rasterR / qMax(1, mp.rasterH));
        contentWDots = qMax(1, static_cast<int>(std::lround(
            static_cast<double>(imgW) * hdpi / dpi)));
        contentHDots = qMax(1, static_cast<int>(std::lround(
            static_cast<double>(imgH) * mp.pageUnit / dpi)));
    } else {
        contentWDots = qMax(1, static_cast<int>(std::lround(
            static_cast<double>(imgW) * mode->xDPI / dpi)));
        contentHDots = qMax(1, static_cast<int>(std::lround(
            static_cast<double>(imgH) * mode->yDPI / dpi)));
    }

    // ---- 1) RGB(A) → CMYK（ICC）----
    QString srcRgb, srcCmyk, destCmyk;
    prs.colorProfiles(job.modeId, &srcRgb, &srcCmyk, &destCmyk);
    QString useDst = mode->colorCorrection ? destCmyk : QString();
    if (!mode->colorCorrection)
        useDst.clear();

    IccTransform icc;
    bool iccReady = false;
    QString iccErr;
    const QByteArray rgbProfile = prs.loadIcc(srcRgb);
    const QByteArray dstProfile = prs.loadIcc(useDst.isEmpty() ? srcCmyk : useDst);
    if (!rgbProfile.isEmpty() && !dstProfile.isEmpty())
        iccReady = icc.createRgbToCmyk(rgbProfile, dstProfile, &iccErr);

    // ---- 1.5) 灰度轴标定 LUT（由 oracle RGB 中性灰探针拟合，见 tools/color_tools/fit_gray_calib.py）----
    QByteArray calibGray;   // 4*256: C,M,Y,K 的 v_icc -> v_oracle
    {
        QString calibDir = resolveResourceDir(QStringLiteral("color"));
        const QString calibPath = calibDir.isEmpty()
                                      ? QString()
                                      : QDir(calibDir).filePath(QStringLiteral("calib_gray.bin"));
        QFile cf(calibPath);
        if (cf.exists() && cf.open(QIODevice::ReadOnly)) {
            const QByteArray d = cf.readAll();
            cf.close();
            if (d.size() >= 1024)
                calibGray = QByteArray(d.constData(), 1024);
        }
    }

    // ---- 1.6) RGB 9³ 三维 LUT（蒙泰 mode2 实测反解，T3/Lead 提供；缺失则静默回退 ICC 路径）----
    //   * 只用于 A3-DTF-1390（prs version 3）；
    //   * 灰度像素（r==g==b）仍走 ICC + calib_gray（保留已验收的灰度精度）；
    //   * MTR_NO_CUBE_LUT=1 强制回退旧路径；MTR_CUBE_LUT=<path> 可覆盖 LUT 文件路径（A/B 用）。
    RgbCubeLut cubeLut;
    bool cubeEnabled = (prs.version == 3) && !envEnabled("MTR_NO_CUBE_LUT");
    if (cubeEnabled) {
        QString cubePath;
        const QByteArray envPath = qgetenv("MTR_CUBE_LUT");
        if (!envPath.isEmpty())
            cubePath = QString::fromLocal8Bit(envPath);
        else
            cubePath = RgbCubeLut::defaultPath();
        QString cubeErr;
        if (!cubeLut.load(cubePath, &cubeErr)) {
            if (envEnabled("MTR_VERBOSE"))
                qWarning("mtr: rgb cube lut not loaded (%s); fallback to ICC path",
                         qPrintable(cubeErr));
        } else if (envEnabled("MTR_VERBOSE")) {
            qInfo("mtr: rgb cube 9x9x9 lut loaded: %s", qPrintable(cubePath));
        }
    }
    const bool cubeReady = cubeLut.isReady();
    // 实验开关：灰度也走 3D LUT（A/B 对比用，默认走 ICC+calib_gray）
    const bool cubeForGray = envEnabled("MTR_CUBE_GRAY");

    QVector<uint8_t> cmyk(static_cast<qsizetype>(imgW) * imgH * 4, 0);
    for (int y = 0; y < imgH; ++y) {
        const uint8_t *line = image.constScanLine(y);
        uint8_t *dst = cmyk.data() + static_cast<qsizetype>(y) * imgW * 4;
        for (int x = 0; x < imgW; ++x, dst += 4) {
            int r = line[x * 4 + 0];
            int g = line[x * 4 + 1];
            int b = line[x * 4 + 2];
            const int a = line[x * 4 + 3];
            // 透明语义（T3 实测，docs/color_pipeline.md §1）：
            //   readTransparency=true 时 alpha 参与：
            //     - a==0：透明区**不产生墨**（DTF 默认；白底由白墨层承担）
            //     - 0<a<255：按 alpha 与白底合成（边缘淡出）
            //   readTransparency=false：忽略 alpha，透明区按 RGB 内容处理（若为黑则印黑）
            if (a < 255 && job.readTransparency) {
                if (a == 0) {
                    dst[0] = dst[1] = dst[2] = dst[3] = 0;
                    continue;
                }
                r = (r * a + 255 * (255 - a) + 127) / 255;
                g = (g * a + 255 * (255 - a) + 127) / 255;
                b = (b * a + 255 * (255 - a) + 127) / 255;
            }
            const bool isGray = (r == g && g == b);
            // 非灰度像素优先走 9³ 3D LUT；灰度像素保留 ICC+calib_gray 已验收路径
            // （若 ICC 不可用，灰度也用 3D LUT 兜底，优于朴素互补）。
            // 实验开关 MTR_CUBE_GRAY=1：灰度也走 3D LUT（A/B 对比用，默认不启用）。
            if (cubeReady && (!isGray || !iccReady || cubeForGray)) {
                unsigned char cubeOut[4] = {0, 0, 0, 0};
                if (cubeLut.lookup(r, g, b, cubeOut)) {
                    dst[0] = cubeOut[0];
                    dst[1] = cubeOut[1];
                    dst[2] = cubeOut[2];
                    dst[3] = cubeOut[3];
                    continue;
                }
            }
            if (iccReady) {
                unsigned char rgb[3] = {static_cast<unsigned char>(r),
                                        static_cast<unsigned char>(g),
                                        static_cast<unsigned char>(b)};
                unsigned char out[4] = {0, 0, 0, 0};
                if (!icc.transform(rgb, out, 3, 4)) {
                    out[0] = static_cast<unsigned char>(255 - r);
                    out[1] = static_cast<unsigned char>(255 - g);
                    out[2] = static_cast<unsigned char>(255 - b);
                }
                dst[0] = out[0]; dst[1] = out[1]; dst[2] = out[2]; dst[3] = out[3];
                if (calibGray.size() >= 1024) {
                    for (int ci = 0; ci < 4; ++ci)
                        dst[ci] = static_cast<uint8_t>(static_cast<unsigned char>(calibGray.at(ci * 256 + dst[ci])));
                }
            } else {
                // 无 ICC 兜底：朴素互补
                dst[0] = static_cast<uint8_t>(255 - r);
                dst[1] = static_cast<uint8_t>(255 - g);
                dst[2] = static_cast<uint8_t>(255 - b);
                dst[3] = static_cast<uint8_t>(
                    qMax(0, qMin(255 - r, qMin(255 - g, 255 - b)) - 128) * 2);
            }
        }
    }

    // ---- 2) 重采样到内容点阵尺寸 ----
    QVector<uint8_t> cmykBig(static_cast<qsizetype>(contentWDots) * contentHDots * 4);
    for (int c = 0; c < 4; ++c) {
        QVector<uint8_t> ch(static_cast<qsizetype>(imgW) * imgH);
        for (int i = 0; i < imgW * imgH; ++i)
            ch[i] = cmyk[i * 4 + c];
        const QVector<uint8_t> big = resampleNearest(ch, imgW, imgH, contentWDots, contentHDots);
        for (int i = 0; i < contentWDots * contentHDots; ++i)
            cmykBig[i * 4 + c] = big[i];
    }

    // ---- 3) 加网（FM stochastic 2bit）----
    Screen screen;
    QString screenErr;
    QString screenDir = resolveResourceDir(QStringLiteral("screen"));
    if (screenDir.isEmpty() || !QFileInfo::exists(screenDir + QStringLiteral("/screen_meta.json")))
        screenDir = QFileInfo(job.prsPath).absolutePath() + QStringLiteral("/screen");
    if (!screen.load(screenDir, &screenErr))
        screen.useFallback(64);

    QVector<InkPlane> planes;
    auto addInkPlane = [&](int ink) {
        InkPlane p;
        p.ink = ink;
        p.ink8.resize(static_cast<qsizetype>(contentWDots) * contentHDots);
        planes.append(p);
        return planes.size() - 1;
    };

    QVector<uint8_t> levels(static_cast<qsizetype>(contentWDots) * contentHDots);
    if (mode->planes <= 4) {
        for (int c = 0; c < 4; ++c) {
            QVector<uint8_t> ink(levels.size());
            for (int i = 0; i < levels.size(); ++i)
                ink[i] = cmykBig[i * 4 + c];
            addInkPlane(c); // 顺序 C,M,Y,K
            screen.dither(ink, contentWDots, contentHDots, c, &levels);
            planes.last().ink8 = levels; // 复用：ink8 此刻存 level（0..3），后面统一打包
        }
    } else {
        // 6-plane：K,C,M,Y 先加网；W1/W2 由 inputColorEditor 决定
        const int order[4] = {INK_K, INK_C, INK_M, INK_Y};
        const int srcIdx[4] = {3, 0, 1, 2};
        for (int i = 0; i < 4; ++i) {
            QVector<uint8_t> ink(levels.size());
            for (int k = 0; k < levels.size(); ++k)
                ink[k] = cmykBig[k * 4 + srcIdx[i]];
            addInkPlane(order[i]);
            const int screenCh = qBound(0, srcIdx[i], 3);
            screen.dither(ink, contentWDots, contentHDots, screenCh, &levels);
            planes.last().ink8 = levels;
        }
        // W1/W2（白墨通道数 = planes - 4：H13 5-plane 只有 W1；A3 6-plane 有 W1/W2）
        const int whiteCount = qBound(0, mode->planes - 4, 2);
        for (int w = 0; w < whiteCount; ++w) {
            const int ink = (w == 0) ? INK_W1 : INK_W2;
            bool enabled = false;
            bool full = true;
            for (const WhiteInkSpec &s : job.inputColorEditor) {
                if (s.inkName.compare(w == 0 ? QStringLiteral("W1") : QStringLiteral("W2"),
                                      Qt::CaseInsensitive) == 0) {
                    enabled = true;
                    full = (s.mode != QLatin1String("color"));
                    break;
                }
            }
            // 注意：oracle 实测——没有 inputColorEditor(W1) 参数时 W1 平面为全 0
            //（H13 mode0 probe_black_64 样本 W1 ink=0）；因此不要默认启用。
            addInkPlane(ink);
            QVector<uint8_t> &lvl = planes.last().ink8;
            lvl.resize(levels.size());
            for (int i = 0; i < levels.size(); ++i) {
                bool on = enabled && (full || (cmykBig[i * 4] | cmykBig[i * 4 + 1] |
                                               cmykBig[i * 4 + 2] | cmykBig[i * 4 + 3]));
                lvl[i] = on ? 3 : 0;
            }
        }
    }

    // ---- 4) 结果 ----
    result->width = contentWDots;
    result->height = contentHDots;
    result->xDPI = mode->xDPI;
    result->yDPI = mode->yDPI;
    result->xDPI = mode->xDPI;
    result->planes.clear();
    for (const InkPlane &p : planes) {
        DevicePlane dp;
        dp.name = inkName(p.ink);
        dp.width = contentWDots;
        dp.height = contentHDots;
        dp.data = p.ink8;
        result->planes.append(dp);
    }
    return true;
}

namespace {

// 把 0..3 level 行打包成 2bit 行（bpl 字节）
void pack2BitRow(const uint8_t *row, int width, uint8_t *dst, int bpl)
{
    std::memset(dst, 0, static_cast<size_t>(bpl));
    for (int x = 0; x < width; ++x)
        dst[x >> 2] |= static_cast<uint8_t>((row[x] & 0x03) << (6 - 2 * (x & 3)));
}

bool writeEscp2(const RipJob &job, const PrsConfig &prs, const PrsMode &mode,
                const RipResult &result, QString *err)
{
    Q_UNUSED(prs);
    const Escp2ModeParams mp = escp2ModeParams(mode.modeId);

    // 颜色码 -> 墨水名（4-plane 与 6-plane 的映射不同，实测见 docs/prn_escp2.md）
    auto codeToInk = [&](int code) -> QString {
        if (mp.planes <= 4) {
            switch (code) {
            case 0x04: return QStringLiteral("K");
            case 0x00: return QStringLiteral("C");
            case 0x12: return QStringLiteral("M");
            case 0x11: return QStringLiteral("Y");
            default: return QString();
            }
        }
        switch (code) {
        case 0x12: return QStringLiteral("W2");
        case 0x11: return QStringLiteral("W1");
        case 0x00: return QStringLiteral("K");
        case 0x02: return QStringLiteral("C");
        case 0x01: return QStringLiteral("M");
        case 0x04: return QStringLiteral("Y");
        default: return QString();
        }
    };

    Escp2PageRaster page;
    page.widthDots = result.width;
    page.heightDots = result.height;
    page.planes.clear();
    for (int code : mp.colorCodes) {
        const QString ink = codeToInk(code);
        QVector<uint8_t> plane;
        for (const DevicePlane &dp : result.planes) {
            if (dp.name == ink) { plane = dp.data; break; }
        }
        if (plane.isEmpty())
            plane = QVector<uint8_t>(static_cast<qsizetype>(page.widthDots) * page.heightDots, 0);
        page.planes.append(plane);
    }

    Escp2Config cfg;
    cfg.jobName = QByteArray("MAINTOPRINT");
    cfg.hostName = QByteArray("Maintop Host");

    Escp2LayoutInfo info;
    return writeEscp2Prn(job.prnPath, mp, page, cfg, &info, err);
}

bool writeHssf(const RipJob &job, const PrsConfig &prs, const PrsMode &mode,
               const RipResult &result, QString *err)
{
    Q_UNUSED(prs);
    HssfConfig hc;
    hc.xDPI = static_cast<uint32_t>(mode.xDPI);
    hc.yDPI = static_cast<uint32_t>(mode.yDPI);
    hc.colorPlane = static_cast<uint32_t>(qMax(1, result.planes.size()));
    hc.dotBits = 0;      // 与 oracle 样本对齐：reserved[0..2] = 0（板卡侧 pass 不由此决定）
    hc.passCount = 0;
    hc.rowsPerStore = 0;
    hc.planeOrder.clear();
    // H13 平面顺序：K,C,M,Y,W1
    static const int order[5] = {INK_K, INK_C, INK_M, INK_Y, INK_W1};
    for (int i = 0; i < 5; ++i) {
        for (int pi = 0; pi < result.planes.size(); ++pi) {
            if (result.planes.at(pi).name == inkName(order[i])) {
                hc.planeOrder.append(pi);
                break;
            }
        }
    }
    HssfWriter writer(hc);
    QVector<QVector<uint8_t>> planes;
    for (int pi = 0; pi < result.planes.size(); ++pi)
        planes.append(result.planes.at(pi).data);
    const QByteArray prn = writer.build(result.width, result.height, planes);

    QFile f(job.prnPath);
    if (!f.open(QIODevice::WriteOnly)) {
        if (err) *err = QStringLiteral("cannot write prn: %1").arg(job.prnPath);
        return false;
    }
    f.write(prn);
    f.close();
    return true;
}

} // namespace

bool RipEngine::run(const RipJob &job, QString *err)
{
    // 1) .prs
    PrsConfig prs;
    QString perr;
    if (!job.prsPath.isEmpty())
        prs.load(job.prsPath, &perr);

    const PrsMode *mode = prs.mode(job.modeId);
    PrsMode fallback;
    if (!mode) {
        fallback.modeId = job.modeId;
        fallback.xDPI = 720;
        fallback.yDPI = 720;
        fallback.planes = 4;
        fallback.pageUnit = 720;
        fallback.marginM = 555;
        fallback.advance = 79;
        fallback.blockRows = 90;
        fallback.p0Offset = 640;
        fallback.uA = fallback.uV = fallback.uH = 4;
        fallback.rasterR = 1440; fallback.rasterV = 16; fallback.rasterH = 2;
        mode = &fallback;
    }

    // 1.5) 未验证模式告警：加网 tile 与灰度标定目前仅对 A3 mode2(720x720) 实测验证；
    //      m5/m7/m9（高质量档）未验证，结果仅作"可打印"近似，勿用于验收。
    if (prs.version == 3 && job.modeId >= 4) {
        qWarning("mtr: modeId=%d 的加网 tile/色彩标定尚未验证（仅 mode2 验证通过）；"
                 "输出可用但非逐像素保证。", job.modeId);
    }

    // 2) 图像
    QImage image;
    if (!image::loadRgba(job.inputPath, &image, err))
        return false;
    // 2.5) rotate：蒙泰 0/180（180 = 水平+垂直镜像，用于 DTF 转印膜取向）
    if (qRound(job.rotate) % 360 == 180)
        image = image.mirrored(true, true);

    // 3) 设备平面
    RipResult result;
    if (!buildDevicePlanes(job, prs, image, &result, err))
        return false;

    // 4) 调试导出
    if (!m_planeDumpDir.isEmpty()) {
        QDir().mkpath(m_planeDumpDir);
        for (const DevicePlane &p : result.planes) {
            QImage img(p.width, p.height, QImage::Format_RGB888);
            for (int y = 0; y < p.height; ++y) {
                uint8_t *line = img.scanLine(y);
                for (int x = 0; x < p.width; ++x) {
                    const int v = 255 - p.data[static_cast<qsizetype>(y) * p.width + x] * 85;
                    line[x * 3 + 0] = static_cast<uint8_t>(v);
                    line[x * 3 + 1] = static_cast<uint8_t>(v);
                    line[x * 3 + 2] = static_cast<uint8_t>(v);
                }
            }
            img.save(QDir(m_planeDumpDir).filePath(p.name + QStringLiteral(".png")));
        }
    }

    // 5) 编码
    const bool isEscp2 = (prs.version == 3) || (job.prsPath.contains(QLatin1String("A3"), Qt::CaseInsensitive));
    if (isEscp2)
        return writeEscp2(job, prs, *mode, result, err);
    return writeHssf(job, prs, *mode, result, err);
}

} // namespace mtr
