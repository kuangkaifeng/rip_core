// ============================================================================
// prn_reconstruct.cpp —— ESC/P2 PRN 反解实现
//
// 文件结构（蒙泰 A3-DTF-1390）：
//   00 00 00 1B 01
//   @EJL 1284.4\n / @EJL     \n
//   ESC ( R 08 00 <data 8: 00 "REMOTE1">
//   TI/JS/JH/SN/PP/MI/DP/US/US 记录（2 字节 tag + u16 len + data）
//   1B 00 00 00（退出远程）
//   命令区：ESC @ / ESC ( G / ESC ( U / ESC U / ESC ( i / ESC ( K / ESC ( e /
//           ESC ( D / ESC ( c / ESC ( S / ESC ( m / ESC ( V
//   [可选 ESC ( v 初值]
//   光栅块：{ ESC ( v adv } 然后每记录 ESC ( $ 04 00 <u32> + ESC i color comp depth
//           nL nH mL mH + RLE 数据 + 0D
//   尾部：0C + ESC @ + ESC( R + "REMOTE1" + LD + JE + 1B 00 00 00
// ============================================================================
#include "core/decode/prn_reconstruct.h"

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QtEndian>
#include <algorithm>
#include <cstring>

#include "core/encode/layout_escp2.h"
#include "core/encode/plane_pack.h"

namespace mtr {

namespace {

constexpr uint8_t kEsc = 0x1B;

uint16_t rdU16(const QByteArray &d, int off)
{
    if (off < 0 || off + 2 > d.size()) return 0;
    return static_cast<uint16_t>(static_cast<uint8_t>(d[off])) |
           static_cast<uint16_t>(static_cast<uint8_t>(d[off + 1]) << 8);
}

uint32_t rdU32(const QByteArray &d, int off)
{
    if (off < 0 || off + 4 > d.size()) return 0;
    return static_cast<uint32_t>(static_cast<uint8_t>(d[off])) |
           (static_cast<uint32_t>(static_cast<uint8_t>(d[off + 1])) << 8) |
           (static_cast<uint32_t>(static_cast<uint8_t>(d[off + 2])) << 16) |
           (static_cast<uint32_t>(static_cast<uint8_t>(d[off + 3])) << 24);
}

int32_t rdI32(const QByteArray &d, int off)
{
    return static_cast<int32_t>(rdU32(d, off));
}

// 2bit MSB-first 解包到一行（宽度 widthDots 个 dot）
void unpack2BitRow(const uint8_t *src, int srcBytes, int widthDots, uint8_t *dst)
{
    const int n = qMin(widthDots, srcBytes * 4);
    for (int i = 0; i < n; ++i) {
        const int b = src[i >> 2];
        dst[i] = static_cast<uint8_t>((b >> (6 - 2 * (i & 3))) & 3);
    }
    for (int i = n; i < widthDots; ++i) dst[i] = 0;
}

} // namespace

QByteArray rleDecodeBytes(const QByteArray &d, int offset, int expected, int *consumed)
{
    QByteArray out;
    out.reserve(expected);
    int i = offset;
    const int n = d.size();
    while (out.size() < expected && i < n) {
        const uint8_t c = static_cast<uint8_t>(d[i++]);
        if (c <= 127) {
            const int cnt = c + 1;
            const int avail = qMin(cnt, n - i);
            out.append(d.constData() + i, avail);
            i += avail;
        } else {
            const int cnt = 257 - c;
            if (i >= n) break;
            out.append(cnt, d[i++]);
            if (out.size() > expected) out.truncate(expected);
        }
    }
    if (consumed) *consumed = i - offset;
    return out;
}

// ---------------------------------------------------------------------------
// 解析
// ---------------------------------------------------------------------------
bool PrnReconstructor::parse(const QString &prnPath, Escp2JobInfo *job, QString *err)
{
    if (!job) return false;
    QFile f(prnPath);
    if (!f.open(QIODevice::ReadOnly)) {
        if (err) *err = QStringLiteral("cannot open prn: %1").arg(prnPath);
        return false;
    }
    const QByteArray d = f.readAll();
    f.close();
    *job = Escp2JobInfo();

    // ---- 1) ENTER D4 ----
    static const uint8_t enterD4[5] = {0x00, 0x00, 0x00, 0x1B, 0x01};
    if (d.size() < 20 || std::memcmp(d.constData(), enterD4, 5) != 0) {
        if (err) *err = QStringLiteral("not an ESC/P2 EJL job (bad magic)");
        return false;
    }
    int pos = 5;
    // ---- 2) 两行 @EJL ----
    for (int line = 0; line < 2; ++line) {
        const int e = d.indexOf('\n', pos);
        if (e < 0) {
            if (err) *err = QStringLiteral("unterminated @EJL header");
            return false;
        }
        pos = e + 1;
    }
    // ---- 3) 远程模式 ----
    static const uint8_t remoteEnter[5] = {kEsc, 0x28, 0x52, 0x08, 0x00};
    if (d.size() < pos + 13 || std::memcmp(d.constData() + pos, remoteEnter, 5) != 0 ||
        std::memcmp(d.constData() + pos + 6, "REMOTE1", 7) != 0) {
        if (err) *err = QStringLiteral("expected ESC(R REMOTE1 at 0x%1").arg(pos, 0, 16);
        return false;
    }
    pos += 13;
    while (pos + 4 <= d.size()) {
        if (d[pos] == 0x1B && d[pos + 1] == 0x00 && d[pos + 2] == 0x00 && d[pos + 3] == 0x00) {
            pos += 4;
            break;
        }
        const QByteArray tag = d.mid(pos, 2);
        const int len = rdU16(d, pos + 2);
        if (pos + 4 + len > d.size()) {
            if (err) *err = QStringLiteral("truncated remote tag at 0x%1").arg(pos, 0, 16);
            return false;
        }
        const QByteArray data = d.mid(pos + 4, len);
        if (tag == "TI") { job->ti = data; job->hasTi = true; }
        else if (tag == "JS") { job->js = data; job->hasJs = true; }
        else if (tag == "JH") { job->jh = data; job->hasJh = true; }
        pos += 4 + len;
    }

    // ---- 4) 命令区 ----
    bool sawU = false, sawD = false, sawC = false, sawS = false;
    while (pos < d.size()) {
        if (d[pos] != kEsc) break;
        const uint8_t c2 = static_cast<uint8_t>(d[pos + 1]);
        if (c2 == 0x40) { pos += 2; continue; }              // ESC @
        if (c2 == 0x55) { pos += 3; continue; }              // ESC U n
        if (c2 == 0x28) {
            if (pos + 5 > d.size()) break;
            const uint8_t letter = static_cast<uint8_t>(d[pos + 2]);
            const int len = rdU16(d, pos + 3);
            if (letter == 0x24) break;                        // ESC( $ -> 光栅区
            if (pos + 5 + len > d.size()) break;
            const QByteArray payload = d.mid(pos + 5, len);
            switch (letter) {
            case 0x55: {   // ESC ( U: uA,uV,uH, unit u16
                if (len >= 5) {
                    job->uA = static_cast<uint8_t>(payload[0]);
                    job->uV = static_cast<uint8_t>(payload[1]);
                    job->uH = static_cast<uint8_t>(payload[2]);
                    job->unit = rdU16(payload, 3);
                    job->pageUnit = job->uA ? job->unit / job->uA : 720;
                    job->rasterHDpi = job->uH ? job->unit / job->uH : 720;
                }
                sawU = true;
                break;
            }
            case 0x44: {   // ESC ( D: rasterR u16, rasterV, rasterH
                if (len >= 4) {
                    job->rasterR = rdU16(payload, 0);
                    job->rasterV = static_cast<uint8_t>(payload[2]);
                    job->rasterH = static_cast<uint8_t>(payload[3]);
                    job->rasterVDpi = job->rasterV ? job->rasterR / job->rasterV : 90;
                    job->rasterHDpi = job->rasterH ? job->rasterR / job->rasterH : 720;
                }
                sawD = true;
                break;
            }
            case 0x63: {   // ESC ( c
                if (len >= 8) {
                    job->pageFormatA = rdI32(payload, 0);
                    job->pageFormatB = rdI32(payload, 4);
                    job->pageMargin = -job->pageFormatA;
                }
                sawC = true;
                break;
            }
            case 0x53: {   // ESC ( S
                if (len >= 8) {
                    job->paperWidth = rdU32(payload, 0);
                    job->paperHeight = rdU32(payload, 4);
                }
                sawS = true;
                break;
            }
            case 0x4B:     // ESC ( K color mode
                if (len >= 2) job->colorMode = static_cast<uint8_t>(payload[1]);
                break;
            case 0x65:     // ESC ( e dot size
                if (len >= 2) job->dotSize = static_cast<uint8_t>(payload[1]);
                break;
            case 0x76:     // ESC ( v：首块前的初值（顶部空白跳过，金样本=150）
                if (len >= 4) job->initialPos += static_cast<int>(rdU32(payload, 0));
                break;
            default:
                break;
            }
            pos += 5 + len;
            continue;
        }
        // 其它 ESC xx：未知，跳过 2 字节
        job->warnings << QStringLiteral("unknown ESC %1 in command region @0x%2")
                             .arg(c2, 2, 16, QLatin1Char('0')).arg(pos, 0, 16);
        pos += 2;
    }
    if (!sawU && !sawD) {
        if (err) *err = QStringLiteral("command region not found (no ESC(U/ESC(D))");
        return false;
    }
    if (job->rasterVDpi <= 0) job->rasterVDpi = 90;
    if (job->rasterHDpi <= 0) job->rasterHDpi = 720;
    if (job->pageUnit <= 0) job->pageUnit = 720;
    job->rowStep = qMax(1, job->pageUnit / job->rasterVDpi);

    // ---- 5) 光栅区 ----
    QVector<int> advances;                 // 各块前 ESC(v（不含首块初值）
    int pendingAdvance = -1;
    int currentBlock = -1;
    const int firstRecordOffset = pos;     // 首条记录（或首个 ESC( $）的文件偏移
    Q_UNUSED(firstRecordOffset);
    while (pos < d.size()) {
        if (static_cast<uint8_t>(d[pos]) == 0x0C) {      // FF -> 尾部
            break;
        }
        if (static_cast<uint8_t>(d[pos]) != kEsc) {
            job->warnings << QStringLiteral("stray byte 0x%1 @0x%2")
                                 .arg(static_cast<uint8_t>(d[pos]), 2, 16, QLatin1Char('0'))
                                 .arg(pos, 0, 16);
            pos += 1;
            continue;
        }
        const uint8_t c2 = static_cast<uint8_t>(d[pos + 1]);
        if (c2 == 0x28) {
            const uint8_t letter = static_cast<uint8_t>(d[pos + 2]);
            const int len = rdU16(d, pos + 3);
            if (pos + 5 + len > d.size()) break;
            if (letter == 0x76) {                        // ESC ( v -> 新块
                pendingAdvance = static_cast<int>(rdU32(d, pos + 5));
                pos += 5 + len;
                continue;
            }
            if (letter == 0x24) {                        // ESC ( $
                pos += 5 + len;
                continue;                                // 紧随的 ESC i 里记录
            }
            pos += 5 + len;
            continue;
        }
        if (c2 == 0x69) {                                // ESC i 记录
            if (pos + 9 > d.size()) break;
            Escp2RecordInfo rec;
            rec.color = static_cast<uint8_t>(d[pos + 2]);
            rec.comp = static_cast<uint8_t>(d[pos + 3]);
            rec.depth = static_cast<uint8_t>(d[pos + 4]);
            rec.n = rdU16(d, pos + 5);
            rec.m = rdU16(d, pos + 7);
            rec.dataOffset = pos + 9;
            const int need = rec.n * rec.m;
            int consumed = 0;
            const QByteArray raw = rleDecodeBytes(d, rec.dataOffset, need, &consumed);
            rec.dataLen = consumed;
            int next = rec.dataOffset + consumed;
            if (next < d.size() && static_cast<uint8_t>(d[next]) == 0x0D) ++next;
            if (currentBlock < 0) {
                currentBlock = 0;
                job->blockRecordStart << 0;
                if (pendingAdvance > 0) {
                    job->initialPos += pendingAdvance;   // 首块前的 ESC(v
                    pendingAdvance = -1;
                }
            } else if (pendingAdvance >= 0) {
                advances << pendingAdvance;
                currentBlock += 1;
                job->blockRecordStart << job->records.size();
                pendingAdvance = -1;
            }
            rec.block = currentBlock;
            job->records << rec;
            job->rawData << raw;
            pos = next;
            continue;
        }
        pos += 2;
    }
    job->advances = advances;
    job->decoded = true;

    // ---- 6) 位置/颜色/模式 ----
    const int blocks = job->blockRecordStart.size();
    if (blocks <= 0) {
        // 无光栅块（纯白作业）：仍有 p0/尺寸信息
    }
    job->positions.resize(blocks);
    int p = job->initialPos;
    for (int k = 0; k < blocks; ++k) {
        if (k > 0) p += advances.value(k - 1, 0);
        job->positions[k] = p;
    }
    if (!job->records.isEmpty()) {
        // 第一块的颜色/记录顺序
        const int end = blocks > 1 ? job->blockRecordStart[1] : job->records.size();
        for (int i = job->blockRecordStart[0]; i < end; ++i)
            job->colorOrder << job->records[i].color;
        job->planes = job->colorOrder.size();
    }
    // 模式识别（pageUnit + 记录数 + ESC(D.h，见 docs/prn_escp2.md §8）
    int modeId = -1;
    if (job->pageUnit == 720) {
        if (job->planes == 6) modeId = (job->rasterH == 4) ? 5 : 3;
        else if (job->planes == 4) modeId = 2;
    } else if (job->pageUnit == 360) {
        modeId = (job->planes == 6) ? 1 : 0;
    } else if (job->pageUnit == 1440) {
        modeId = (job->rasterH == 4) ? 7 : 9;
    }
    job->modeIdGuess = modeId;
    if (modeId < 0) modeId = 2;
    const Escp2ModeParams mp = escp2ModeParams(modeId);
    job->rowStep = mp.rowStep;
    job->recordOffsets = mp.recordOffsets;
    // 内容尺寸（文档 §7.2）：ESC(S) 宽 = content_w_units；ESC(c) 两参数之和 = 内容高
    job->contentWidthDots = static_cast<int>(job->paperWidth);
    job->contentHeightDots = job->pageFormatB + job->pageFormatA;
    if (job->contentHeightDots < 0) job->contentHeightDots = 0;
    // content_w_units -> content_w_dots（按 hdpi/pageUnit 换算；m2/m3 两者相同）
    job->contentWidthDots = static_cast<int>(
        (static_cast<qint64>(job->contentWidthDots) * qMax(1, job->rasterHDpi)
         + mp.pageUnit / 2) / qMax(1, mp.pageUnit));
    // P0 是模式常量（文档 §7.2，不是图像尺寸的函数）
    job->p0 = mp.baseP0;
    return true;
}

// ---------------------------------------------------------------------------
// 页面 raster 重建
// ---------------------------------------------------------------------------
bool PrnReconstructor::decode(const QString &prnPath, PrnPageRaster *page,
                              Escp2JobInfo *jobOut, QString *err,
                              int modeIdOverride)
{
    Escp2JobInfo job;
    if (!parse(prnPath, &job, err))
        return false;
    int modeId = modeIdOverride >= 0 ? modeIdOverride : job.modeIdGuess;
    if (modeId < 0) modeId = 2;
    const Escp2ModeParams mp = escp2ModeParams(modeId);
    if (modeIdOverride >= 0) {
        job.recordOffsets = mp.recordOffsets;
        job.rowStep = mp.rowStep;
        job.p0 = mp.baseP0;
    }
    if (jobOut) *jobOut = job;

    PrnPageRaster pr;
    if (job.records.isEmpty()) {
        // 纯白作业：仍返回空 raster
        pr.rows = 0;
        pr.widthDots = 0;
        if (page) *page = pr;
        return true;
    }
    // 页面行范围
    int maxP = 0, maxW = 0;
    for (int k = 0; k < job.blockRecordStart.size(); ++k) {
        const int end = (k + 1 < job.blockRecordStart.size())
                            ? job.blockRecordStart[k + 1] : job.records.size();
        const int m = job.records[job.blockRecordStart[k]].m;
        const int posMin = job.positions[k];
        maxP = qMax(maxP, posMin + job.rowStep * (m - 1));
        for (int i = job.blockRecordStart[k]; i < end; ++i)
            maxW = qMax(maxW, job.records[i].n * 4);
    }
    // 记录偏移会把物理行上移，最多 +16 余量
    pr.rows = maxP + 18;
    pr.widthDots = maxW;
    pr.colors = job.colorOrder;
    for (int c : job.colorOrder)
        pr.planes[c] = QVector<uint8_t>(static_cast<qsizetype>(pr.rows) * pr.widthDots, 0);
    pr.inkUnion = QVector<uint8_t>(static_cast<qsizetype>(pr.rows) * pr.widthDots, 0);

    QVector<uint8_t> cover(static_cast<qsizetype>(pr.rows) * pr.widthDots, 0);
    QVector<uint8_t> nonZero(static_cast<qsizetype>(pr.rows) * pr.widthDots, 0);
    QVector<uint8_t> rowBuf(pr.widthDots);
    for (int k = 0; k < job.blockRecordStart.size(); ++k) {
        const int end = (k + 1 < job.blockRecordStart.size())
                            ? job.blockRecordStart[k + 1] : job.records.size();
        int ri = 0;
        for (int i = job.blockRecordStart[k]; i < end; ++i, ++ri) {
            const Escp2RecordInfo &rec = job.records[i];
            const int off = job.recordOffsets.value(ri, 0);
            const QByteArray &raw = job.rawData[i];
            const uint8_t *rp = reinterpret_cast<const uint8_t *>(raw.constData());
            QVector<uint8_t> &plane = pr.planes[rec.color];
            for (int r = 0; r < rec.m; ++r) {
                const int recorded = job.positions[k] + job.rowStep * r;
                const int p = recorded - off;
                if (p < 0 || p >= pr.rows) continue;
                if (r * rec.n + rec.n > raw.size()) break;
                unpack2BitRow(rp + static_cast<qsizetype>(r) * rec.n, rec.n,
                              pr.widthDots, rowBuf.data());
                const qsizetype base = static_cast<qsizetype>(p) * pr.widthDots;
                for (int x = 0; x < pr.widthDots; ++x) {
                    const uint8_t v = rowBuf[x];
                    if (!v) continue;
                    const qsizetype idx = base + x;
                    cover[idx] = static_cast<uint8_t>(qMin(255, cover[idx] + 1));
                    nonZero[idx] = static_cast<uint8_t>(qMin(255, nonZero[idx] + 1));
                    if (v > plane[idx]) plane[idx] = v;
                    if (v > pr.inkUnion[idx]) pr.inkUnion[idx] = v;
                }
            }
        }
    }
    for (qsizetype i = 0; i < cover.size(); ++i) {
        if (cover[i] > 1) ++pr.overlapPixels;
        if (nonZero[i] > 1) ++pr.conflictPixels;
    }
    if (page) *page = pr;
    return true;
}

bool PrnReconstructor::extractContentPlanes(const QString &prnPath, int modeId,
                                            QVector<QVector<uint8_t>> *planes,
                                            int *widthDots, int *heightDots,
                                            Escp2JobInfo *jobOut, QString *err)
{
    Escp2JobInfo job;
    if (!parse(prnPath, &job, err))
        return false;
    if (jobOut) *jobOut = job;
    const Escp2ModeParams mp = escp2ModeParams(modeId >= 0 ? modeId : job.modeIdGuess);
    const int rs = qMax(1, mp.rowStep);
    const int p0 = mp.baseP0;
    const int contentW = job.contentWidthDots;
    const int contentH = job.contentHeightDots;
    if (contentW <= 0 || contentH <= 0) {
        if (err) *err = QStringLiteral("cannot derive content size (W=%1 H=%2)")
                            .arg(contentW).arg(contentH);
        return false;
    }
    const int recCount = qMax(1, mp.colorCodes.size());
    QVector<QVector<uint8_t>> out(recCount);
    for (int i = 0; i < recCount; ++i)
        out[i] = QVector<uint8_t>(static_cast<qsizetype>(contentW) * contentH, 0);

    QVector<uint8_t> rowBuf(contentW);
    // 记录在块内的序号 -> 平面序号（用第一块记录顺序；即 mp.colorCodes 顺序）
    for (int k = 0; k < job.blockRecordStart.size(); ++k) {
        const int end = (k + 1 < job.blockRecordStart.size())
                            ? job.blockRecordStart[k + 1] : job.records.size();
        int ri = 0;
        for (int i = job.blockRecordStart[k]; i < end; ++i, ++ri) {
            const Escp2RecordInfo &rec = job.records[i];
            const int planeIdx = qMin(ri, recCount - 1);
            const int off = mp.recordOffsets.value(planeIdx, 0);
            const QByteArray &raw = job.rawData[i];
            const uint8_t *rp = reinterpret_cast<const uint8_t *>(raw.constData());
            QVector<uint8_t> &plane = out[planeIdx];
            const int srcW = rec.n * 4;
            const int copyW = qMin(contentW, srcW);
            for (int r = 0; r < rec.m; ++r) {
                const int recorded = job.positions[k] + rs * r;
                const int contentRow = recorded - off - p0;
                if (contentRow < 0 || contentRow >= contentH) continue;
                unpack2BitRow(rp + static_cast<qsizetype>(r) * rec.n, rec.n,
                              copyW, rowBuf.data());
                uint8_t *dst = plane.data() + static_cast<qsizetype>(contentRow) * contentW;
                for (int x = 0; x < copyW; ++x)
                    if (rowBuf[x] > dst[x]) dst[x] = rowBuf[x];
            }
        }
    }
    if (planes) *planes = out;
    if (widthDots) *widthDots = contentW;
    if (heightDots) *heightDots = contentH;
    return true;
}

// ---------------------------------------------------------------------------
// 导出/工具
// ---------------------------------------------------------------------------
QImage PrnReconstructor::planeToImage(const QVector<uint8_t> &plane, int width, int height)
{
    QImage img(qMax(1, width), qMax(1, height), QImage::Format_RGB888);
    for (int y = 0; y < height; ++y) {
        uint8_t *line = img.scanLine(y);
        const uint8_t *src = plane.constData() + static_cast<qsizetype>(y) * width;
        for (int x = 0; x < width; ++x) {
            const int v = 255 - src[x] * 85;
            line[x * 3 + 0] = static_cast<uint8_t>(v);
            line[x * 3 + 1] = static_cast<uint8_t>(v);
            line[x * 3 + 2] = static_cast<uint8_t>(v);
        }
    }
    return img;
}

bool PrnReconstructor::exportBmps(const PrnPageRaster &page, const QString &outDir, QString *err)
{
    QDir().mkpath(outDir);
    for (int c : page.colors) {
        const QImage img = planeToImage(page.planes.value(c), page.widthDots, page.rows);
        const QString path = QDir(outDir).filePath(QStringLiteral("plane_%1.bmp")
                                                       .arg(c, 2, 16, QLatin1Char('0')));
        if (!img.save(path, "BMP")) {
            if (err) *err = QStringLiteral("cannot save %1").arg(path);
            return false;
        }
    }
    if (!page.inkUnion.isEmpty()) {
        const QImage img = planeToImage(page.inkUnion, page.widthDots, page.rows);
        img.save(QDir(outDir).filePath(QStringLiteral("ink_union.bmp")), "BMP");
    }
    return true;
}

Escp2Config PrnReconstructor::jobInfoToConfig(const Escp2JobInfo &job)
{
    Escp2Config cfg;
    // JS: 0x00 + name + 0 填充
    if (job.js.size() > 1) {
        QByteArray name = job.js.mid(1);
        const int z = name.indexOf('\0');
        if (z >= 0) name.truncate(z);
        if (!name.isEmpty()) cfg.jobName = name;
    }
    // JH: 6 个 0 + hostname(12)
    if (job.jh.size() > 6) {
        QByteArray host = job.jh.mid(6);
        const int z = host.indexOf('\0');
        if (z >= 0) host.truncate(z);
        if (!host.isEmpty()) cfg.hostName = host;
    }
    // TI: 00 年(BE) 月 日 时 分 秒
    if (job.ti.size() >= 8) {
        const int year = (static_cast<uint8_t>(job.ti[1]) << 8) |
                         static_cast<uint8_t>(job.ti[2]);
        const QDate date(year, static_cast<uint8_t>(job.ti[3]),
                         static_cast<uint8_t>(job.ti[4]));
        const QTime time(static_cast<uint8_t>(job.ti[5]),
                         static_cast<uint8_t>(job.ti[6]),
                         static_cast<uint8_t>(job.ti[7]));
        if (date.isValid() && time.isValid()) cfg.time = QDateTime(date, time);
    }
    return cfg;
}

} // namespace mtr
