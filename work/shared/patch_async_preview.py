# -*- coding: utf-8 -*-
# ---------- mainwindow.h ----------
p = r"D:\work\RIP核心分析\src\gui\mainwindow.h"
t = open(p, encoding="utf-8").read()
t = t.replace("class QThread;", "class QThread;\nclass QCloseEvent;")
t = t.replace("""protected:
    void resizeEvent(QResizeEvent *e) override;""",
"""protected:
    void resizeEvent(QResizeEvent *e) override;
    void closeEvent(QCloseEvent *e) override;""")
t = t.replace("    void onChannelChanged(int idx);\n    void onThreadFinished();",
              "    void onChannelChanged(int idx);\n    void onThreadFinished();\n    void onPreviewFinished();")
t = t.replace("""    void updatePreview();
    void fitPreview();""",
"""    void updatePreview();
    void applyPreview(class PreviewDataHolder *unused) = delete; // 占位（不使用）
    void fitPreview();""")
t = t.replace("""    QThread *m_thread = nullptr;""",
"""    QThread *m_thread = nullptr;
    QThread *m_previewThread = nullptr;""")
t = t.replace("""    QImage m_original;
    QMap<QString, QImage> m_channels;
    QImage m_composite;""",
"""    QImage m_original;         // 原图（RIP 用，全尺寸）
    QImage m_originalPreview;  // 原图预览（缩到 <=1600）
    QMap<QString, QImage> m_channels;
    QImage m_composite;""")
open(p, "w", encoding="utf-8", newline="").write(t)
print("header updated")

# ---------- mainwindow.cpp ----------
p = r"D:\work\RIP核心分析\src\gui\mainwindow.cpp"
t = open(p, encoding="utf-8").read()

# 1) includes
t = t.replace("#include <QThread>", "#include <QCloseEvent>\n#include <QThread>")

# 2) PreviewThread 类（放在 RipThread 之后）
anchor = "QString modeLabel(const mtr::PrsMode &m)"
preview_cls = '''// 后台预览线程：解码 PRN + 渲染（避免大图卡住 GUI）
class PreviewThread : public QThread
{
public:
    PreviewThread(QString prnPath, QImage original, int modeId, QObject *parent = nullptr)
        : QThread(parent), m_prn(std::move(prnPath)), m_original(std::move(original)),
          m_modeId(modeId) {}
    bool ok = false;
    QString err;
    qint64 elapsedMs = 0;
    mtr::gui::PreviewData pv;

protected:
    void run() override
    {
        QElapsedTimer t;
        t.start();
        ok = mtr::gui::renderPrnPreview(m_prn, m_original, &pv, &err, m_modeId);
        elapsedMs = t.elapsed();
    }

private:
    QString m_prn;
    QImage m_original;
    int m_modeId = -1;
};

'''
t = t.replace(anchor, preview_cls + anchor)

# 3) setBusy 光标修复
old_busy = """void MainWindow::setBusy(bool busy)
{
    m_generateBtn->setEnabled(!busy);
    m_previewBtn->setEnabled(!busy);
    m_generateBtn->setText(busy ? QStringLiteral("RIP 中…") : QStringLiteral("▶ RIP 生成 PRN"));
    QApplication::setOverrideCursor(busy ? Qt::WaitCursor : Qt::ArrowCursor);
    if (!busy) QApplication::restoreOverrideCursor();
}"""
new_busy = """void MainWindow::setBusy(bool busy)
{
    m_generateBtn->setEnabled(!busy);
    m_previewBtn->setEnabled(!busy);
    m_generateBtn->setText(busy ? QStringLiteral("RIP 中…") : QStringLiteral("▶ RIP 生成 PRN"));
    // 注意：不能成对写 setOverrideCursor/restore——之前每次生成都会在光标栈里残留一个
    // WaitCursor，导致界面看起来"一直卡住"（光标永远是等待图标）。
    if (busy) {
        QApplication::setOverrideCursor(Qt::WaitCursor);
    } else {
        QApplication::restoreOverrideCursor();
    }
}"""
assert old_busy in t
t = t.replace(old_busy, new_busy)

# 4) updatePreview 改为异步
old_up = """void MainWindow::updatePreview()
{
    if (m_lastPrn.isEmpty()) return;
    mtr::gui::PreviewData pv;
    QString err;
    if (!mtr::gui::renderPrnPreview(m_lastPrn, m_original, &pv, &err, m_hasMode ? m_mode.modeId : -1)) {
        m_infoLabel->setText(QStringLiteral("预览失败: %1").arg(err));
        log(QStringLiteral("预览失败: %1").arg(err));
        return;
    }
    m_composite = pv.composite;
    m_channels = pv.channels;
    m_channelCombo->blockSignals(true);
    const QString cur = m_channelCombo->currentData().toString();
    m_channelCombo->clear();
    m_channelCombo->addItem(QStringLiteral("合成（模拟打印）"), QStringLiteral("__composite__"));
    m_channelCombo->addItem(QStringLiteral("原图"), QStringLiteral("__original__"));
    for (auto it = pv.channels.constBegin(); it != pv.channels.constEnd(); ++it) {
        if (!it.value().isNull())
            m_channelCombo->addItem(QStringLiteral("通道 %1").arg(it.key()), it.key());
    }
    const int idx = m_channelCombo->findData(cur);
    m_channelCombo->setCurrentIndex(idx >= 0 ? idx : 0);
    m_channelCombo->blockSignals(false);
    m_infoLabel->setText(QStringLiteral("格式 %1 · 页面 %2×%3 点 · 通道 %4 · 文件 %5 字节")
                             .arg(pv.format)
                             .arg(pv.widthDots)
                             .arg(pv.heightDots)
                             .arg(pv.channels.keys().join(QLatin1Char('/')))
                             .arg(QFileInfo(m_lastPrn).size()));
    log(QStringLiteral("预览完成：%1 %2×%3").arg(pv.format).arg(pv.widthDots).arg(pv.heightDots));
    fitPreview();
}"""
new_up = """void MainWindow::updatePreview()
{
    if (m_lastPrn.isEmpty()) return;
    if (m_previewThread && m_previewThread->isRunning()) {
        log(QStringLiteral("预览正在生成中，请稍候…"));
        return;
    }
    m_infoLabel->setText(QStringLiteral("预览生成中…"));
    QApplication::setOverrideCursor(Qt::BusyCursor);
    auto *th = new PreviewThread(m_lastPrn, m_original,
                                 m_hasMode ? m_mode.modeId : -1, this);
    m_previewThread = th;
    connect(th, &QThread::finished, this, &MainWindow::onPreviewFinished);
    th->start();
}

void MainWindow::onPreviewFinished()
{
    auto *th = static_cast<PreviewThread *>(m_previewThread);
    const bool ok = th ? th->ok : false;
    const QString err = th ? th->err : QStringLiteral("内部错误");
    const qint64 ms = th ? th->elapsedMs : 0;
    const mtr::gui::PreviewData pv = th ? th->pv : mtr::gui::PreviewData();
    if (th) th->deleteLater();
    m_previewThread = nullptr;
    QApplication::restoreOverrideCursor();

    if (!ok) {
        m_infoLabel->setText(QStringLiteral("预览跳过/失败: %1").arg(err));
        log(QStringLiteral("预览跳过/失败（%1 ms）: %2").arg(ms).arg(err));
        return;
    }
    m_composite = pv.composite;
    m_channels = pv.channels;
    if (!pv.original.isNull())
        m_originalPreview = pv.original;
    m_channelCombo->blockSignals(true);
    const QString cur = m_channelCombo->currentData().toString();
    m_channelCombo->clear();
    m_channelCombo->addItem(QStringLiteral("合成（模拟打印）"), QStringLiteral("__composite__"));
    m_channelCombo->addItem(QStringLiteral("原图"), QStringLiteral("__original__"));
    for (auto it = pv.channels.constBegin(); it != pv.channels.constEnd(); ++it) {
        if (!it.value().isNull())
            m_channelCombo->addItem(QStringLiteral("通道 %1").arg(it.key()), it.key());
    }
    const int idx = m_channelCombo->findData(cur);
    m_channelCombo->setCurrentIndex(idx >= 0 ? idx : 0);
    m_channelCombo->blockSignals(false);
    m_infoLabel->setText(QStringLiteral("格式 %1 · 内容 %2×%3 点 · 通道 %4 · 文件 %5 字节 · 预览 %6 ms")
                             .arg(pv.format)
                             .arg(pv.widthDots)
                             .arg(pv.heightDots)
                             .arg(pv.channels.keys().join(QLatin1Char('/')))
                             .arg(QFileInfo(m_lastPrn).size())
                             .arg(ms));
    log(QStringLiteral("预览完成：%1 %2×%3（%4 ms）")
            .arg(pv.format).arg(pv.widthDots).arg(pv.heightDots).arg(ms));
    fitPreview();
}"""
assert old_up in t
t = t.replace(old_up, new_up)

# 5) fitPreview 原图用缩放副本
t = t.replace("    if (key == QLatin1String(\"__original__\")) img = m_original;",
              "    if (key == QLatin1String(\"__original__\")) img = m_originalPreview;")

# 6) 载入图像时保存预览缩略图
old_load = """        loadInputImageInto(p, &m_original, [this](const QString &m) { log(m); });
    });"""
new_load = """        loadInputImageInto(p, &m_original, [this](const QString &m) { log(m); });
        if (!m_original.isNull())
            m_originalPreview = m_original.scaled(1600, 1600, Qt::KeepAspectRatio,
                                                  Qt::SmoothTransformation);
    });"""
assert old_load in t
t = t.replace(old_load, new_load)
t = t.replace("""    loadInputImageInto(p, &m_original, [this](const QString &m) { log(m); });
}""",
"""    loadInputImageInto(p, &m_original, [this](const QString &m) { log(m); });
    if (!m_original.isNull())
        m_originalPreview = m_original.scaled(1600, 1600, Qt::KeepAspectRatio,
                                              Qt::SmoothTransformation);
}""")

# 7) closeEvent + 析构等待
t = t.replace("""MainWindow::~MainWindow()
{
    if (m_thread && m_thread->isRunning()) {
        m_thread->terminate();
        m_thread->wait(2000);
    }
}""",
"""MainWindow::~MainWindow()
{
    for (QThread *th : {m_thread, m_previewThread}) {
        if (th && th->isRunning()) {
            th->requestInterruption();
            th->wait(3000);
        }
    }
}""")
t = t.replace("""void MainWindow::setBusy(bool busy)""",
"""void MainWindow::closeEvent(QCloseEvent *e)
{
    if ((m_thread && m_thread->isRunning()) ||
        (m_previewThread && m_previewThread->isRunning())) {
        QMessageBox::information(this, QStringLiteral("请稍候"),
                                 QStringLiteral("RIP / 预览仍在后台处理中，请等待完成后再关闭窗口。"));
        e->ignore();
        return;
    }
    QMainWindow::closeEvent(e);
}

void MainWindow::setBusy(bool busy)""")

open(p, "w", encoding="utf-8", newline="").write(t)
print("mainwindow async preview + cursor fix done")
