# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\main.cpp"
t = open(p, encoding="utf-8").read()

# includes
if '#include "core/color/icc_transform.h"' not in t:
    t = t.replace('#include "core/prs_config.h"',
                  '#include "core/prs_config.h"\n#include "core/color/icc_transform.h"')

# declaration
t = t.replace("static int runInfo(const QStringList &args);",
              "static int runInfo(const QStringList &args);\nstatic int runGray(const QStringList &args);")
# dispatch
t = t.replace('    if (cmd == QLatin1String("info"))\n        return runInfo(rest);',
              '    if (cmd == QLatin1String("info"))\n        return runInfo(rest);\n    if (cmd == QLatin1String("gray"))\n        return runGray(rest);')

# implementation appended before runInfo
fn = r'''
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

'''
t = t.replace("static int runInfo(const QStringList &args)\n{", fn + "static int runInfo(const QStringList &args)\n{")
open(p, "w", encoding="utf-8", newline="").write(t)
print("gray command added")
