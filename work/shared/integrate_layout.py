# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace('#include "core/encode/escp2_writer.h"',
              '#include "core/encode/escp2_writer.h"\n#include "core/encode/layout_escp2.h"')
start = t.index("bool writeEscp2(const RipJob &job, const PrsConfig &prs, const PrsMode &mode,")
end = t.index("bool writeHssf(const RipJob &job, const PrsConfig &prs, const PrsMode &mode,")
new_fn = r'''bool writeEscp2(const RipJob &job, const PrsConfig &prs, const PrsMode &mode,
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

'''
t = t[:start] + new_fn + t[end:]
open(p, "w", encoding="utf-8", newline="").write(t)
print("rip_engine integrated with layout_escp2")
