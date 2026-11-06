// ============================================================================
// mtr_prncheck —— ESC/P2 PRN 反解与验证工具（T5 交付）
//
// 用法：
//   mtr_prncheck info     <prn>
//   mtr_prncheck raster   <prn> [--out dir]
//   mtr_prncheck compare  <ref.prn> <gen.prn>
//   mtr_prncheck roundtrip <ref.prn> [--out out.prn] [--mode N]
//
// roundtrip：把参考 PRN 反解成"内容平面"，再用我们的 layout+encoder 重新编码，
// 然后比较结构/内容平面/页面 raster/字节差异 —— 这是版面几何的闭环验证。
// ============================================================================
#include <QCoreApplication>
#include <QCommandLineParser>
#include <QDir>
#include <QFile>
#include <QMap>
#include <QString>
#include <QStringList>
#include <QTextStream>
#include <cstdio>

#include "core/decode/prn_reconstruct.h"
#include "core/encode/layout_escp2.h"

using namespace mtr;

static QString colorName(int code, int planes = 4)
{
    if (planes >= 6) {
        switch (code) {
        case 0x00: return QStringLiteral("K");
        case 0x01: return QStringLiteral("M");
        case 0x02: return QStringLiteral("C");
        case 0x04: return QStringLiteral("Y");
        case 0x11: return QStringLiteral("W2");
        case 0x12: return QStringLiteral("W1");
        default:   return QStringLiteral("?");
        }
    }
    switch (code) {                 // 4 色模式：04=K, 00=C, 12=M, 11=Y
    case 0x04: return QStringLiteral("K");
    case 0x00: return QStringLiteral("C");
    case 0x12: return QStringLiteral("M");
    case 0x11: return QStringLiteral("Y");
    default:   return QStringLiteral("?");
    }
}
static QString colorNames(const QVector<int> &codes)
{
    QStringList l;
    const int planes = codes.size();
    for (int c : codes) l << QStringLiteral("%1(0x%2)").arg(colorName(c, planes))
                                 .arg(c, 2, 16, QLatin1Char('0'));
    return l.join(QLatin1Char(','));
}

static int cmdInfo(const QString &path)
{
    Escp2JobInfo job;
    QString err;
    if (!PrnReconstructor::parse(path, &job, &err)) {
        fprintf(stderr, "parse failed: %s\n", qPrintable(err));
        return 4;
    }
    QTextStream ts(stdout);
    ts << "file: " << path << "\n";
    ts << "pageUnit=" << job.pageUnit << " uA/uV/uH=" << job.uA << "/" << job.uV << "/" << job.uH
       << " rasterR=" << job.rasterR << " rasterV=" << job.rasterV << " rasterH=" << job.rasterH
       << " (vDpi=" << job.rasterVDpi << ", hDpi=" << job.rasterHDpi << ")\n";
    ts << "ESC(c)=(" << job.pageFormatA << "," << job.pageFormatB << ") marginM=" << job.pageMargin
       << " ESC(S)=(" << job.paperWidth << "," << job.paperHeight << ")\n";
    ts << "modeIdGuess=" << job.modeIdGuess << " planes=" << job.planes << " rowStep=" << job.rowStep
       << " colors=" << colorNames(job.colorOrder) << "\n";
    ts << "content=" << job.contentWidthDots << "x" << job.contentHeightDots
       << " p0=" << job.p0 << " initialPos=" << job.initialPos << "\n";
    ts << "blocks=" << job.blockRecordStart.size() << " records=" << job.records.size()
       << " warnings=" << job.warnings.size() << "\n";
    ts << "positions:";
    for (int i = 0; i < job.positions.size(); ++i) ts << " " << job.positions[i];
    ts << "\nadvances:";
    for (int i = 0; i < job.advances.size(); ++i) ts << " " << job.advances[i];
    ts << "\n";
    for (int i = 0; i < job.warnings.size() && i < 10; ++i) ts << "  ! " << job.warnings[i] << "\n";
    return 0;
}

static int cmdRaster(const QString &path, const QString &outDir)
{
    PrnPageRaster page;
    Escp2JobInfo job;
    QString err;
    if (!PrnReconstructor::decode(path, &page, &job, &err)) {
        fprintf(stderr, "decode failed: %s\n", qPrintable(err));
        return 4;
    }
    QTextStream ts(stdout);
    ts << "page raster: " << page.widthDots << "x" << page.rows
       << " colors=" << colorNames(page.colors)
       << " overlapPixels=" << page.overlapPixels << " conflictPixels=" << page.conflictPixels << "\n";
    if (!outDir.isEmpty()) {
        if (!PrnReconstructor::exportBmps(page, outDir, &err)) {
            fprintf(stderr, "export failed: %s\n", qPrintable(err));
            return 4;
        }
        ts << "exported to " << outDir << "\n";
    }
    return 0;
}

// 比较两份 PRN：结构、内容平面、页面 raster
static int cmdCompare(const QString &refPath, const QString &genPath)
{
    Escp2JobInfo a, b;
    QString err;
    if (!PrnReconstructor::parse(refPath, &a, &err) || !PrnReconstructor::parse(genPath, &b, &err)) {
        fprintf(stderr, "parse failed: %s\n", qPrintable(err));
        return 4;
    }
    QTextStream ts(stdout);
    auto eq = [](int x, int y) { return x == y ? "OK" : "DIFF"; };
    ts << "== structure ==\n";
    ts << " blocks: " << a.blockRecordStart.size() << " vs " << b.blockRecordStart.size()
       << " " << eq(a.blockRecordStart.size(), b.blockRecordStart.size()) << "\n";
    ts << " pageUnit: " << a.pageUnit << " vs " << b.pageUnit << "\n";
    ts << " margin: " << a.pageMargin << " vs " << b.pageMargin << "\n";
    ts << " content: " << a.contentWidthDots << "x" << a.contentHeightDots << " vs "
       << b.contentWidthDots << "x" << b.contentHeightDots << "\n";
    ts << " p0: " << a.p0 << " vs " << b.p0 << " " << eq(a.p0, b.p0) << "\n";
    ts << " colors: " << colorNames(a.colorOrder) << " vs " << colorNames(b.colorOrder) << "\n";
    const int ncom = qMin(a.records.size(), b.records.size());
    int nd = 0;
    for (int i = 0; i < ncom; ++i) {
        const Escp2RecordInfo &ra = a.records[i], &rb = b.records[i];
        if (ra.n != rb.n || ra.m != rb.m || ra.color != rb.color) {
            if (nd < 6) ts << "  rec " << i << " DIFF: (" << ra.color << "," << ra.n << "," << ra.m
                           << ") vs (" << rb.color << "," << rb.n << "," << rb.m << ")\n";
            ++nd;
        }
    }
    if (a.records.size() != b.records.size())
        ts << "  record count DIFF: " << a.records.size() << " vs " << b.records.size() << "\n";
    ts << " records mismatched: " << nd << "/" << ncom << "\n";

    // 内容平面比较（按 mode 用同一套几何还原）
    const int modeA = a.modeIdGuess >= 0 ? a.modeIdGuess : 2;
    const int modeB = b.modeIdGuess >= 0 ? b.modeIdGuess : 2;
    QVector<QVector<uint8_t>> pa, pb;
    int wa = 0, ha = 0, wb = 0, hb = 0;
    const int colorPlanes = qMax(a.planes, b.planes);
    if (!PrnReconstructor::extractContentPlanes(refPath, modeA, &pa, &wa, &ha, nullptr, &err)
        || !PrnReconstructor::extractContentPlanes(genPath, modeB, &pb, &wb, &hb, nullptr, &err)) {
        fprintf(stderr, "extract failed: %s\n", qPrintable(err));
        return 4;
    }
    ts << "== content planes ==\n";
    ts << " size: " << wa << "x" << ha << " vs " << wb << "x" << hb << "\n";
    const int W = qMin(wa, wb), H = qMin(ha, hb);
    const int planes = qMin(pa.size(), pb.size());
    int totalInk = 0, diffInk = 0, totalDots = 0;
    for (int c = 0; c < planes; ++c) {
        const QVector<uint8_t> &A = pa[c], &B = pb[c];
        int inkA = 0, inkB = 0, diff = 0;
        for (int y = 0; y < H; ++y) {
            for (int x = 0; x < W; ++x) {
                const uint8_t va = A[y * wa + x], vb = B[y * wb + x];
                if (va) ++inkA;
                if (vb) ++inkB;
                if (va != vb) ++diff;
                ++totalDots;
            }
        }
        totalInk += inkA;
        diffInk += diff;
        ts << "  plane " << c << " (" << colorName(a.colorOrder.value(c, 0), colorPlanes)
           << "): inkA=" << inkA << " inkB=" << inkB << " diff=" << diff
           << " (" << (totalDots ? 100.0 * diff / double(W * H) : 0.0) << "% of area)\n";
    }
    // patch: diffInk/totalDots 已在上面按行累计，这里输出总体面积差异率
    const double areaRate = totalDots ? 100.0 * diffInk / double(totalDots) : 0.0;
    ts << " TOTAL pixel diff rate = " << areaRate << "%  (inkA=" << totalInk << ")\n";
    return 0;
}

static int cmdRoundtrip(const QString &refPath, const QString &outPath, int modeOverride)
{
    Escp2JobInfo job;
    QString err;
    if (!PrnReconstructor::parse(refPath, &job, &err)) {
        fprintf(stderr, "parse failed: %s\n", qPrintable(err));
        return 4;
    }
    const int modeId = modeOverride >= 0 ? modeOverride
                                         : (job.modeIdGuess >= 0 ? job.modeIdGuess : 2);
    QVector<QVector<uint8_t>> planes;
    int W = 0, H = 0;
    if (!PrnReconstructor::extractContentPlanes(refPath, modeId, &planes, &W, &H, nullptr, &err)) {
        fprintf(stderr, "extract failed: %s\n", qPrintable(err));
        return 4;
    }
    const Escp2ModeParams mp = escp2ModeParams(modeId);
    Escp2PageRaster page;
    page.widthDots = W;
    page.heightDots = H;
    page.planes = planes;
    Escp2Config cfg = PrnReconstructor::jobInfoToConfig(job);
    QByteArray prn;
    Escp2LayoutInfo layout;
    if (!buildEscp2Prn(mp, page, cfg, &prn, &layout, &err)) {
        fprintf(stderr, "build failed: %s\n", qPrintable(err));
        return 4;
    }
    const QString out = outPath.isEmpty() ? (refPath + QStringLiteral(".regen.prn")) : outPath;
    QFile f(out);
    if (!f.open(QIODevice::WriteOnly) || f.write(prn) != prn.size()) {
        fprintf(stderr, "cannot write %s\n", qPrintable(out));
        return 4;
    }
    f.close();
    QTextStream ts(stdout);
    ts << "regen: " << out << " (" << prn.size() << " B)  ref: " << job.contentWidthDots
       << "x" << job.contentHeightDots << " p0(ref)=" << job.p0 << " p0(gen)=" << layout.p0
       << " blocks(ref)=" << job.blockRecordStart.size() << " blocks(gen)=" << layout.blockCount
       << "\n";

    // 字节比较
    QFile fr(refPath);
    fr.open(QIODevice::ReadOnly);
    const QByteArray ref = fr.readAll();
    fr.close();
    const int n = qMin(ref.size(), prn.size());
    int byteDiff = 0, firstDiff = -1;
    for (int i = 0; i < n; ++i) {
        if (ref[i] != prn[i]) {
            ++byteDiff;
            if (firstDiff < 0) firstDiff = i;
        }
    }
    ts << "byte compare: ref=" << ref.size() << " gen=" << prn.size()
       << " commonDiff=" << byteDiff << " firstDiff=0x" << QString::number(firstDiff, 16) << "\n";
    // 注意：这里不再嵌套调用 cmdCompare（MSVC Release 下嵌套调用会触发
    // QTextStream/局部对象析构崩溃）；需要结构/内容比较请另起一次 compare 命令。
    return 0;
}

static int cmdContent(const QString &prnPath, const QString &outDir, int modeOverride)
{
    Escp2JobInfo job;
    QString err;
    if (!PrnReconstructor::parse(prnPath, &job, &err)) {
        fprintf(stderr, "parse failed: %s\n", qPrintable(err));
        return 4;
    }
    const int modeId = modeOverride >= 0 ? modeOverride
                                         : (job.modeIdGuess >= 0 ? job.modeIdGuess : 2);
    QVector<QVector<uint8_t>> planes;
    int W = 0, H = 0;
    if (!PrnReconstructor::extractContentPlanes(prnPath, modeId, &planes, &W, &H, &job, &err)) {
        fprintf(stderr, "extract failed: %s\n", qPrintable(err));
        return 4;
    }
    const Escp2ModeParams mp = escp2ModeParams(modeId);
    QTextStream ts(stdout);
    ts << "content: " << W << "x" << H << " modeId=" << modeId
       << " planes=" << planes.size() << " colors=" << colorNames(mp.colorCodes) << "\n";
    if (!outDir.isEmpty()) {
        QDir().mkpath(outDir);
        for (int i = 0; i < planes.size(); ++i) {
            const int code = mp.colorCodes.value(i, 0);
            const QString path = QDir(outDir).filePath(
                QStringLiteral("content_%1_%2.w%3h%4.bin")
                    .arg(i).arg(code, 2, 16, QLatin1Char('0')).arg(W).arg(H));
            QFile f(path);
            if (!f.open(QIODevice::WriteOnly) || f.write(QByteArray(
                    reinterpret_cast<const char *>(planes[i].constData()), planes[i].size()))
                != planes[i].size()) {
                fprintf(stderr, "cannot write %s\n", qPrintable(path));
                return 4;
            }
            f.close();
            ts << "  wrote " << path << " (" << planes[i].size() << " B)\n";
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    const QStringList args = QCoreApplication::arguments();
    if (args.size() < 3) {
        fprintf(stderr,
                "usage:\n"
                "  mtr_prncheck info <prn>\n"
                "  mtr_prncheck raster <prn> [--out dir]\n"
                "  mtr_prncheck content <prn> [--out dir] [--mode N]\n"
                "  mtr_prncheck compare <ref.prn> <gen.prn>\n"
                "  mtr_prncheck roundtrip <ref.prn> [--out out.prn] [--mode N]\n");
        return 2;
    }
    const QString cmd = args.at(1);
    QStringList rest = args.mid(2);
    QString outDir, outPath;
    int mode = -1;
    QStringList pos;
    for (int i = 0; i < rest.size(); ++i) {
        if (rest[i] == QLatin1String("--out")) {
            if (i + 1 < rest.size()) { outDir = rest[i + 1]; outPath = rest[i + 1]; i++; }
        } else if (rest[i] == QLatin1String("--mode")) {
            if (i + 1 < rest.size()) { mode = rest[i + 1].toInt(); i++; }
        } else {
            pos << rest[i];
        }
    }
    if (cmd == QLatin1String("info") && pos.size() >= 1)
        return cmdInfo(pos[0]);
    if (cmd == QLatin1String("raster") && pos.size() >= 1)
        return cmdRaster(pos[0], outDir);
    if (cmd == QLatin1String("compare") && pos.size() >= 2)
        return cmdCompare(pos[0], pos[1]);
    if (cmd == QLatin1String("roundtrip") && pos.size() >= 1)
        return cmdRoundtrip(pos[0], outPath, mode);
    if (cmd == QLatin1String("content") && pos.size() >= 1)
        return cmdContent(pos[0], outDir, mode);
    fprintf(stderr, "bad arguments\n");
    return 2;
}
