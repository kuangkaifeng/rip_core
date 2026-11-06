// ============================================================================
// mtr_cli — MainTop Replacement 命令行入口
//
// 用法:
//   mtr_cli rip    --job job.json            # 按蒙泰兼容作业 JSON 生成 prn
//   mtr_cli rip    --input a.png --prn a.prn --prs A3-DTF-1390.prs --mode 2
//   mtr_cli decode --prn a.prn --out dir/    # 解析 prn（验证用）
//   mtr_cli info   --prs x.prs               # 打印 prs 解析结果
//
// 本文件只做参数解析与调度，实际逻辑在 mtr_core。
// ============================================================================
#include <QCoreApplication>
#include <QCommandLineParser>
#include <QString>
#include <QStringList>
#include <QTextStream>
#include <cstdio>

#include "core/rip_engine.h"
#include "core/job_config.h"
#include "core/prs_config.h"
#include "core/color/icc_transform.h"
#include "core/decode/prn_reconstruct.h"
#include "core/debug/prn_decode.h"

static int runRip(const QStringList &args);
static int runDecode(const QStringList &args);
static int runInfo(const QStringList &args);
static int runGray(const QStringList &args);

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    QCoreApplication::setApplicationName(QStringLiteral("mtr_cli"));
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.0"));

    const QStringList args = QCoreApplication::arguments();
    if (args.size() < 2) {
        fprintf(stderr,
                "usage:\n"
                "  mtr_cli rip    --job job.json | --input a.png --prn a.prn --prs x.prs --mode N\n"
                "  mtr_cli decode --prn a.prn [--out dir]\n"
                "  mtr_cli info   --prs x.prs\n");
        return 2;
    }

    const QString cmd = args.at(1);
    const QStringList rest = args.mid(2);
    if (cmd == QLatin1String("rip"))
        return runRip(rest);
    if (cmd == QLatin1String("decode"))
        return runDecode(rest);
    if (cmd == QLatin1String("info"))
        return runInfo(rest);
    if (cmd == QLatin1String("gray"))
        return runGray(rest);

    fprintf(stderr, "unknown command: %s\n", qPrintable(cmd));
    return 2;
}

static QStringList withAppName(const QStringList &args)
{
    QStringList a;
    a.append(QStringLiteral("mtr_cli"));
    a.append(args);
    return a;
}

static int runRip(const QStringList &args)
{
    QCommandLineParser parser;
    parser.addHelpOption();
    QCommandLineOption jobOpt(QStringLiteral("job"), QStringLiteral("MainTop 兼容作业 JSON"), QStringLiteral("file"));
    QCommandLineOption inputOpt(QStringLiteral("input"), QStringLiteral("输入图像"), QStringLiteral("file"));
    QCommandLineOption prnOpt(QStringLiteral("prn"), QStringLiteral("输出 .prn"), QStringLiteral("file"));
    QCommandLineOption prsOpt(QStringLiteral("prs"), QStringLiteral(".prs 打印设置文件"), QStringLiteral("file"));
    QCommandLineOption modeOpt(QStringLiteral("mode"), QStringLiteral("modeId (0..3)"), QStringLiteral("n"));
    QCommandLineOption dumpPlanesOpt(QStringLiteral("dump-planes"), QStringLiteral("调试: 把各通道 2bit 平面导出到目录"), QStringLiteral("dir"));
    parser.addOptions({jobOpt, inputOpt, prnOpt, prsOpt, modeOpt, dumpPlanesOpt});
    parser.parse(withAppName(args));

    mtr::RipJob job;
    if (parser.isSet(jobOpt)) {
        QString err;
        if (!mtr::RipJob::loadFromFile(parser.value(jobOpt), &job, &err)) {
            fprintf(stderr, "job parse failed: %s\n", qPrintable(err));
            return 3;
        }
    } else {
        job.inputPath = parser.value(inputOpt);
        job.prnPath = parser.value(prnOpt);
        job.prsPath = parser.value(prsOpt);
        job.modeId = parser.value(modeOpt).toInt();
    }
    if (job.inputPath.isEmpty() || job.prnPath.isEmpty()) {
        fprintf(stderr, "rip: need --job or (--input and --prn)\n");
        return 2;
    }

    mtr::RipEngine engine;
    if (parser.isSet(dumpPlanesOpt))
        engine.setPlaneDumpDir(parser.value(dumpPlanesOpt));
    QString err;
    if (!engine.run(job, &err)) {
        fprintf(stderr, "rip failed: %s\n", qPrintable(err));
        return 4;
    }
    fprintf(stdout, "rip ok: %s\n", qPrintable(job.prnPath));
    return 0;
}

static int runDecode(const QStringList &args)
{
    QCommandLineParser parser;
    QCommandLineOption prnOpt(QStringLiteral("prn"), QStringLiteral("输入 .prn"), QStringLiteral("file"));
    QCommandLineOption outOpt(QStringLiteral("out"), QStringLiteral("输出目录（导出每色页面 BMP）"), QStringLiteral("dir"));
    QCommandLineOption modeOpt(QStringLiteral("mode"), QStringLiteral("强制 modeId（缺省自动识别）"), QStringLiteral("n"));
    parser.addOptions({prnOpt, outOpt, modeOpt});
    parser.parse(withAppName(args));
    if (!parser.isSet(prnOpt)) {
        fprintf(stderr, "decode: need --prn\n");
        return 2;
    }
    const QString prnPath = parser.value(prnOpt);
    const QString dir = parser.isSet(outOpt) ? parser.value(outOpt) : QString();
    const int mode = parser.isSet(modeOpt) ? parser.value(modeOpt).toInt() : -1;

    // 结构 + 每记录解码 + 页面 raster（T5：src/core/decode/prn_reconstruct）
    mtr::Escp2JobInfo job;
    QString err;
    if (!mtr::PrnReconstructor::parse(prnPath, &job, &err)) {
        fprintf(stderr, "decode failed: %s\n", qPrintable(err));
        return 4;
    }
    mtr::PrnPageRaster page;
    if (!mtr::PrnReconstructor::decode(prnPath, &page, nullptr, &err, mode)) {
        fprintf(stderr, "decode failed: %s\n", qPrintable(err));
        return 4;
    }
    fprintf(stdout,
            "decode ok: %s\n"
            "  modeId=%d content=%dx%d p0=%d rowStep=%d blocks=%d records=%d\n"
            "  ESC(U uA/uV/uH=%d/%d/%d unit=%d  ESC(D r/v/h=%d/%d/%d  vdpi=%d hdpi=%d\n"
            "  ESC(c)=(%d,%d) marginM=%d  ESC(S)=(%u,%u)\n"
            "  page raster=%dx%d colors=%d overlapPixels=%d conflictPixels=%d\n",
            qPrintable(prnPath), job.modeIdGuess, job.contentWidthDots, job.contentHeightDots,
            job.p0, job.rowStep, job.blockRecordStart.size(), job.records.size(),
            job.uA, job.uV, job.uH, job.unit, job.rasterR, job.rasterV, job.rasterH,
            job.rasterVDpi, job.rasterHDpi, job.pageFormatA, job.pageFormatB, job.pageMargin,
            job.paperWidth, job.paperHeight, page.widthDots, page.rows, page.colors.size(),
            page.overlapPixels, page.conflictPixels);
    if (!job.warnings.isEmpty())
        fprintf(stdout, "  warnings=%d (first: %s)\n", job.warnings.size(),
                qPrintable(job.warnings.first()));
    if (!dir.isEmpty()) {
        if (!mtr::PrnReconstructor::exportBmps(page, dir, &err)) {
            fprintf(stderr, "decode export failed: %s\n", qPrintable(err));
            return 4;
        }
        fprintf(stdout, "  page rasters exported to %s\n", qPrintable(dir));
    }
    return 0;
}


// 导出引擎自身的 RGB->CMYK 数值链（t=0..255 中性灰），供灰度标定 LUT 拟合
// 用法: mtr_cli gray --prs x.prs [--mode 2]
static int runGray(const QStringList &args)
{
    QCommandLineParser parser;
    QCommandLineOption prsOpt(QStringLiteral("prs"), QStringLiteral(".prs 文件"), QStringLiteral("file"));
    QCommandLineOption modeOpt(QStringLiteral("mode"), QStringLiteral("modeId"), QStringLiteral("n"), QStringLiteral("2"));
    parser.addOptions({prsOpt, modeOpt});
    parser.parse(withAppName(args));
    if (!parser.isSet(prsOpt)) {
        fprintf(stderr, "gray: need --prs\n");
        return 2;
    }
    const int modeId = parser.value(modeOpt).toInt();
    mtr::PrsConfig cfg;
    QString err;
    if (!cfg.load(parser.value(prsOpt), &err)) {
        fprintf(stderr, "gray: prs parse failed: %s\n", qPrintable(err));
        return 4;
    }
    QString srcRgb, srcCmyk, destCmyk;
    cfg.colorProfiles(modeId, &srcRgb, &srcCmyk, &destCmyk);
    const mtr::PrsMode *m = cfg.mode(modeId);
    const bool useDest = (m && m->colorCorrection && !destCmyk.isEmpty());
    const QByteArray rgbProfile = cfg.loadIcc(srcRgb);
    const QByteArray dstProfile = cfg.loadIcc(useDest ? destCmyk : srcCmyk);
    mtr::IccTransform icc;
    QString ierr;
    bool ready = false;
    if (!rgbProfile.isEmpty() && !dstProfile.isEmpty())
        ready = icc.createRgbToCmyk(rgbProfile, dstProfile, &ierr);
    for (int t = 0; t < 256; ++t) {
        unsigned char in[3] = {static_cast<unsigned char>(t), static_cast<unsigned char>(t),
                               static_cast<unsigned char>(t)};
        unsigned char out[4] = {0, 0, 0, 0};
        if (ready) {
            if (!icc.transform(in, out, 3, 4)) {
                out[0] = static_cast<unsigned char>(255 - t);
                out[1] = static_cast<unsigned char>(255 - t);
                out[2] = static_cast<unsigned char>(255 - t);
            }
        } else {
            out[0] = static_cast<unsigned char>(255 - t);
        }
        fprintf(stdout, "%d %d %d %d %d\n", t, out[0], out[1], out[2], out[3]);
    }
    return 0;
}

static int runInfo(const QStringList &args)
{
    QCommandLineParser parser;
    QCommandLineOption prsOpt(QStringLiteral("prs"), QStringLiteral(".prs 文件"), QStringLiteral("file"));
    parser.addOptions({prsOpt});
    parser.parse(withAppName(args));
    if (!parser.isSet(prsOpt)) {
        fprintf(stderr, "info: need --prs\n");
        return 2;
    }
    mtr::PrsConfig cfg;
    QString err;
    if (!cfg.load(parser.value(prsOpt), &err)) {
        fprintf(stderr, "prs parse failed: %s\n", qPrintable(err));
        return 4;
    }
    QString text;
    QTextStream ts(&text);
    cfg.dump(&ts);
    fputs(qPrintable(text), stdout);
    return 0;
}
