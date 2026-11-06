// ============================================================================
// main.cpp —— mtr RIP Studio（Qt Widgets GUI）
//
// 用法：
//   mtr_gui.exe                         正常打开 GUI
//   mtr_gui.exe --selftest <img> <prs> <modeId> <outDir>
//       无界面自检：生成 PRN + 预览 PNG（供 CI/自动化验证）
// ============================================================================
#include <QApplication>
#include <QDir>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QImageReader>
#include <QTextStream>
#include <QTimer>

#include <cstdio>

#include "core/rip_engine.h"
#include "gui/mainwindow.h"
#include "gui/previewrenderer.h"

namespace {

int runSelftest(const QStringList &args)
{
    auto out = [](const QString &s) {
        fputs(s.toUtf8().constData(), stdout);
        fputc('\n', stdout);
        fflush(stdout);
    };
    if (args.size() < 4) {
        out(QStringLiteral("用法: mtr_gui --selftest <input> <prs> <modeId> <outDir>"));
        return 2;
    }
    const QString input = args.at(0);
    const QString prs = args.at(1);
    const int modeId = args.at(2).toInt();
    const QString outDir = args.at(3);
    if (!QFileInfo::exists(input)) {
        out(QStringLiteral("错误: 输入不存在: %1").arg(input));
        return 2;
    }
    if (!QFileInfo::exists(prs)) {
        out(QStringLiteral("错误: prs 不存在: %1").arg(prs));
        return 2;
    }
    QDir().mkpath(outDir);

    const QFileInfo fi(input);
    mtr::RipJob job;
    job.inputPath = input;
    job.prsPath = prs;
    job.modeId = modeId;
    job.prnPath = QDir(outDir).filePath(fi.completeBaseName() + QStringLiteral("_selftest.prn"));

    mtr::RipEngine engine;
    QString err;
    QElapsedTimer timer;
    timer.start();
    const bool ok = engine.run(job, &err);
    const qint64 ms = timer.elapsed();
    if (!ok) {
        out(QStringLiteral("RIP 失败: %1").arg(err));
        return 3;
    }
    const qint64 size = QFileInfo(job.prnPath).size();
    out(QStringLiteral("RIP OK: %1 (%2 bytes, %3 ms)").arg(job.prnPath).arg(size).arg(ms));

    QImage original;
    QImageReader reader(input);
    original = reader.read();

    mtr::gui::PreviewData pv;
    QString perr;
    if (!mtr::gui::renderPrnPreview(job.prnPath, original, &pv, &perr, modeId)) {
        out(QStringLiteral("预览失败: %1").arg(perr));
        return 4;
    }
    const QString compPath = QDir(outDir).filePath(QStringLiteral("preview_composite.png"));
    pv.composite.save(compPath);
    out(QStringLiteral("预览 OK: %1 (%2×%3, %4)").arg(compPath).arg(pv.widthDots)
            .arg(pv.heightDots).arg(pv.format));
    for (auto it = pv.channels.constBegin(); it != pv.channels.constEnd(); ++it) {
        const QString p = QDir(outDir).filePath(QStringLiteral("preview_%1.png").arg(it.key()));
        it.value().save(p);
        out(QStringLiteral("  通道 %1 -> %2").arg(it.key(), p));
    }
    out(QStringLiteral("SELFTEST OK"));
    return 0;
}

} // namespace

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QCoreApplication::setApplicationName(QStringLiteral("mtr RIP Studio"));
    QCoreApplication::setApplicationVersion(QStringLiteral("1.0.0"));

    const QStringList args = QCoreApplication::arguments();
    if (args.size() >= 2 && args.at(1) == QLatin1String("--selftest"))
        return runSelftest(args.mid(2));

    // --screenshot <out.png> [input prs modeId]：自动载入作业、生成、抓窗口截图
    if (args.size() >= 3 && args.at(1) == QLatin1String("--screenshot")) {
        const QString shot = args.at(2);
        auto *w = new mtr::gui::MainWindow();
        w->show();
        if (args.size() >= 6) {
            const QString out = QDir(QFileInfo(shot).absolutePath())
                                    .filePath(QFileInfo(args.at(3)).completeBaseName() +
                                              QStringLiteral("_shot.prn"));
            w->autoLoad(args.at(3), args.at(4), args.at(5).toInt(), out);
            QTimer::singleShot(400, w, &mtr::gui::MainWindow::autoGenerate);
        }
        QTimer::singleShot(3200, w, [w, shot, &app]() {
            const bool ok = w->grab().save(shot);
            fputs(ok ? "screenshot OK\n" : "screenshot FAILED\n", stdout);
            fflush(stdout);
            app.quit();
        });
        return app.exec();
    }

    mtr::gui::MainWindow w;
    w.show();
    return app.exec();
}
