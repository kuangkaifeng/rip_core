# -*- coding: utf-8 -*-
# ---- mainwindow.h: public 方法 ----
p = r"D:\work\RIP核心分析\src\gui\mainwindow.h"
t = open(p, encoding="utf-8").read()
t = t.replace("""    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow() override;
""",
"""    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow() override;

    // 自动化（--screenshot / --selftest 用）：预填作业并立即生成
    void autoLoad(const QString &input, const QString &prs, int modeId, const QString &output = QString());
    void autoGenerate();
""")
open(p, "w", encoding="utf-8", newline="").write(t)

# ---- mainwindow.cpp: 实现 ----
p = r"D:\work\RIP核心分析\src\gui\mainwindow.cpp"
t = open(p, encoding="utf-8").read()
anchor = "void MainWindow::log(const QString &msg)"
impl = """void MainWindow::autoLoad(const QString &input, const QString &prs, int modeId,
                          const QString &output)
{
    m_inputEdit->setText(input);
    if (m_prsCombo->findText(prs) < 0)
        m_prsCombo->addItem(prs);
    m_prsCombo->setCurrentIndex(m_prsCombo->findText(prs));
    onLoadPrs();
    const int idx = m_modeCombo->findData(modeId);
    if (idx >= 0) m_modeCombo->setCurrentIndex(idx);
    onModeChanged();
    if (!output.isEmpty())
        m_outputEdit->setText(output);
    else if (!input.isEmpty()) {
        const QFileInfo fi(input);
        m_outputEdit->setText(fi.absolutePath() + QLatin1Char('/') +
                              fi.completeBaseName() + QStringLiteral(".prn"));
    }
    loadInputImageInto(input, &m_original, [this](const QString &m) { log(m); });
}

void MainWindow::autoGenerate()
{
    onGenerate();
}

"""
t = t.replace(anchor, impl + anchor)
open(p, "w", encoding="utf-8", newline="").write(t)

# ---- main.cpp: --screenshot 模式 ----
p = r"D:\work\RIP核心分析\src\gui\main.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace("#include <QTextStream>", "#include <QTextStream>\n#include <QTimer>")
old = """    const QStringList args = QCoreApplication::arguments();
    if (args.size() >= 2 && args.at(1) == QLatin1String("--selftest"))
        return runSelftest(args.mid(2));
"""
new = """    const QStringList args = QCoreApplication::arguments();
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
            fputs(ok ? "screenshot OK\\n" : "screenshot FAILED\\n", stdout);
            fflush(stdout);
            app.quit();
        });
        return app.exec();
    }
"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("screenshot mode added")
