# -*- coding: utf-8 -*-
# ---- mainwindow.h ----
p = r"D:\work\RIP核心分析\src\gui\mainwindow.h"
t = open(p, encoding="utf-8").read()
t = t.replace("""    // 供自检模式复用：直接按参数生成 + 预览
    bool runJob(const mtr::RipJob &job, QString *err, qint64 *elapsedMs);

""", "")
open(p, "w", encoding="utf-8", newline="").write(t)

# ---- mainwindow.cpp ----
p = r"D:\work\RIP核心分析\src\gui\mainwindow.cpp"
t = open(p, encoding="utf-8").read()

# 1) 修正 modeLabel（PrsMode 没有 paperSize）
t = t.replace("""QString modeLabel(const mtr::PrsMode &m)
{
    return QStringLiteral("mode %1 · %2×%3 dpi · %4 色 · %5")
        .arg(m.modeId)
        .arg(m.xDPI)
        .arg(m.yDPI)
        .arg(m.planes)
        .arg(m.colorCorrection ? QStringLiteral("校色") : QStringLiteral("直通"))
        + QStringLiteral(" · ") + m.paperSize;
}""",
"""QString modeLabel(const mtr::PrsMode &m)
{
    return QStringLiteral("mode %1 · %2×%3 dpi · %4 色 · %5 · %6")
        .arg(m.modeId)
        .arg(m.xDPI)
        .arg(m.yDPI)
        .arg(m.planes)
        .arg(m.colorCorrection ? QStringLiteral("校色") : QStringLiteral("直通"))
        .arg(m.inkText.isEmpty() ? m.dpiText : m.inkText);
}

void loadInputImageInto(const QString &path, QImage *image, std::function<void(const QString &)> logFn)
{
    QImageReader reader(path);
    const QImage img = reader.read();
    if (img.isNull()) {
        logFn(QStringLiteral("读取图像失败: %1").arg(reader.errorString()));
        return;
    }
    *image = img;
    logFn(QStringLiteral("已载入图像: %1 × %2").arg(img.width()).arg(img.height()));
}""")

# 2) include <functional>, <QTime>
t = t.replace("#include <QVBoxLayout>", "#include <QVBoxLayout>\n#include <QTime>\n#include <functional>")

# 3) onLoadPrs 重写（使用成员字段与 mode()/modes 成员）
old_load = """void MainWindow::onLoadPrs()
{
    const QString p = m_prsCombo->currentText();
    m_modeCombo->clear();
    m_hasMode = false;
    if (!QFileInfo::exists(p)) {
        log(QStringLiteral("未找到 .prs: %1").arg(p));
        return;
    }
    mtr::PrsConfig cfg;
    QString err;
    if (!cfg.load(p, &err)) {
        log(QStringLiteral(".prs 解析失败: %1").arg(err));
        return;
    }
    m_prs = cfg;
    m_prsPath = p;
    log(QStringLiteral(".prs 已加载: %1（版本 %2，%3 个模式）")
            .arg(QFileInfo(p).fileName()).arg(cfg.version()).arg(cfg.modeCount()));
    for (const mtr::PrsMode &m : cfg.modes()) {
        m_modeCombo->addItem(modeLabel(m), m.modeId);
    }
    // 默认选记录 0 对应的模式
    const int rec0 = cfg.modeForRecord(0);
    const int idx = m_modeCombo->findData(rec0 >= 0 ? rec0 : 2);
    if (idx >= 0) m_modeCombo->setCurrentIndex(idx);
}"""
new_load = """void MainWindow::onLoadPrs()
{
    const QString p = m_prsCombo->currentText();
    m_modeCombo->clear();
    m_hasMode = false;
    if (!QFileInfo::exists(p)) {
        log(QStringLiteral("未找到 .prs: %1").arg(p));
        return;
    }
    mtr::PrsConfig cfg;
    QString err;
    if (!cfg.load(p, &err)) {
        log(QStringLiteral(".prs 解析失败: %1").arg(err));
        return;
    }
    m_prs = cfg;
    m_prsPath = p;
    log(QStringLiteral(".prs 已加载: %1（版本 %2，%3 个模式，驱动 %4）")
            .arg(QFileInfo(p).fileName())
            .arg(m_prs.version)
            .arg(m_prs.modes.size())
            .arg(m_prs.driverModule));
    for (const mtr::PrsMode &m : m_prs.modes) {
        m_modeCombo->addItem(modeLabel(m), m.modeId);
    }
    if (m_modeCombo->count() == 0) {
        log(QStringLiteral("警告: .prs 中未解析出模式表"));
        return;
    }
    // 默认：A3 用 mode2（金样本/已验证），H13 用 mode0
    const int def = (m_prs.version == 3) ? 2 : 0;
    int idx = m_modeCombo->findData(def);
    if (idx < 0) idx = 0;
    m_modeCombo->setCurrentIndex(idx);
    onModeChanged();
}"""
assert old_load in t
t = t.replace(old_load, new_load)

# 4) 追加 onModeChanged 实现（放在 onLoadPrs 后面）
anchor = "bool MainWindow::collectJob(mtr::RipJob *job, QString *err)"
impl = """void MainWindow::onModeChanged()
{
    const int id = m_modeCombo->currentData().toInt();
    const mtr::PrsMode *m = m_prs.mode(id);
    if (!m) {
        m_hasMode = false;
        return;
    }
    m_mode = *m;
    m_hasMode = true;
    log(QStringLiteral("当前模式: %1").arg(modeLabel(m_mode)));
}

"""
t = t.replace(anchor, impl + anchor)

# 5) collectJob 修正字段类型
old_cj = """    job->inputPath = input;
    job->prnPath = output;
    job->prsPath = m_prsPath;
    job->modeId = m_modeCombo->currentData().toInt();
    job->rotate = m_rotateCombo->currentData().toInt();
    job->scaleX = m_scaleX->value();
    job->scaleY = m_scaleY->value();
    job->marginL = m_marginL->value();
    job->marginT = m_marginT->value();
    job->marginR = m_marginR->value();
    job->marginB = m_marginB->value();
    job->inkIEMode = m_inkModeCombo->currentData().toInt();
    job->inkIEMarginL = m_dotL->value();
    job->inkIEMarginT = m_dotT->value();
    job->inkIEMarginR = m_dotR->value();
    job->inkIEMarginB = m_dotB->value();
    job->inputColorEditor.clear();"""
new_cj = """    job->inputPath = input;
    job->prnPath = output;
    job->prsPath = m_prsPath;
    job->modeId = m_modeCombo->currentData().toInt();
    job->rotate = m_rotateCombo->currentData().toDouble();
    job->scale = {m_scaleX->value() * 100.0, m_scaleY->value() * 100.0};
    job->margin = {m_marginL->value(), m_marginT->value(),
                   m_marginR->value(), m_marginB->value()};
    job->inkIE.clear();
    {
        mtr::InkIESpec ie;
        ie.index = 4;
        ie.mode = m_inkModeCombo->currentData().toInt() == 0 ? QStringLiteral("invaginate")
                                                             : QStringLiteral("expand");
        ie.dots = {static_cast<double>(m_dotL->value()), static_cast<double>(m_dotT->value()),
                   static_cast<double>(m_dotR->value()), static_cast<double>(m_dotB->value())};
        job->inkIE.append(ie);
    }
    job->inputColorEditor.clear();"""
assert old_cj in t
t = t.replace(old_cj, new_cj)

# 6) 输入图像读取改用辅助函数（替换 lambda emit）
old_lambda = """    connect(m_inputEdit, &QLineEdit::editingFinished, this, [this] {
        const QString p = m_inputEdit->text().trimmed();
        if (p.isEmpty()) return;
        if (m_outputEdit->text().trimmed().isEmpty()) {
            QFileInfo fi(p);
            m_outputEdit->setText(fi.absolutePath() + QLatin1Char('/') +
                                  fi.completeBaseName() + QStringLiteral(".prn"));
        }
        QImageReader reader(p);
        const QImage img = reader.read();
        if (!img.isNull()) {
            m_original = img;
            log(QStringLiteral("已载入图像: %1 × %2").arg(img.width()).arg(img.height()));
        }
    });"""
new_lambda = """    connect(m_inputEdit, &QLineEdit::editingFinished, this, [this] {
        const QString p = m_inputEdit->text().trimmed();
        if (p.isEmpty()) return;
        if (m_outputEdit->text().trimmed().isEmpty()) {
            QFileInfo fi(p);
            m_outputEdit->setText(fi.absolutePath() + QLatin1Char('/') +
                                  fi.completeBaseName() + QStringLiteral(".prn"));
        }
        loadInputImageInto(p, &m_original, [this](const QString &m) { log(m); });
    });"""
assert old_lambda in t
t = t.replace(old_lambda, new_lambda)

# 7) onBrowseInput 不 emit 信号
t = t.replace("""    m_inputEdit->setText(p);
    emit m_inputEdit->editingFinished();""",
"""    m_inputEdit->setText(p);
    if (m_outputEdit->text().trimmed().isEmpty()) {
        QFileInfo fi(p);
        m_outputEdit->setText(fi.absolutePath() + QLatin1Char('/') +
                              fi.completeBaseName() + QStringLiteral(".prn"));
    }
    loadInputImageInto(p, &m_original, [this](const QString &m) { log(m); });""")

# 8) resizeEvent 中 m_composite 为空时也 fit
t = t.replace("""    QMainWindow::resizeEvent(e);
    if (!m_composite.isNull()) fitPreview();""",
"""    QMainWindow::resizeEvent(e);
    fitPreview();""")

# 9) 禁用引擎未实现的参数控件（scale/margin/inkIE），rotate 已实现
anchor2 = "    m_generateBtn = new QPushButton(QStringLiteral(\"▶ RIP 生成 PRN\"), optBox);"
extra = """    // 引擎当前实现范围：rotate 180 / 白墨 / mode 已生效；scale、margin、inkIE 为预留参数
    for (QWidget *w : {static_cast<QWidget *>(m_scaleX), static_cast<QWidget *>(m_scaleY),
                       static_cast<QWidget *>(m_marginL), static_cast<QWidget *>(m_marginT),
                       static_cast<QWidget *>(m_marginR), static_cast<QWidget *>(m_marginB),
                       static_cast<QWidget *>(m_inkModeCombo), static_cast<QWidget *>(m_dotL),
                       static_cast<QWidget *>(m_dotT), static_cast<QWidget *>(m_dotR),
                       static_cast<QWidget *>(m_dotB)}) {
        w->setEnabled(false);
        w->setToolTip(QStringLiteral("预留参数：当前引擎未实现（蒙泰参数已解析，待后续版本）"));
    }

"""
t = t.replace(anchor2, extra + anchor2)
open(p, "w", encoding="utf-8", newline="").write(t)
print("mainwindow fixed")

# ---- mainwindow.h: 增加 onModeChanged + loadInputImageInto 声明 ----
p = r"D:\work\RIP核心分析\src\gui\mainwindow.h"
t = open(p, encoding="utf-8").read()
t = t.replace("    void onLoadPrs();", "    void onLoadPrs();\n    void onModeChanged();")
open(p, "w", encoding="utf-8", newline="").write(t)
print("mainwindow.h updated")

# ---- 引擎：实现 rotate 180 ----
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
old_rot = """    // 2) 图像
    QImage image;
    if (!image::loadRgba(job.inputPath, &image, err))
        return false;"""
new_rot = """    // 2) 图像
    QImage image;
    if (!image::loadRgba(job.inputPath, &image, err))
        return false;
    // 2.5) rotate：蒙泰 0/180（180 = 水平+垂直镜像，用于 DTF 转印膜取向）
    if (qRound(job.rotate) % 360 == 180)
        image = image.mirrored(true, true);"""
assert old_rot in t
t = t.replace(old_rot, new_rot)
open(p, "w", encoding="utf-8", newline="").write(t)
print("engine rotate implemented")
