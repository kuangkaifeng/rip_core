#include "gui/mainwindow.h"

#include <QApplication>
#include <QComboBox>
#include <QDateTime>
#include <QDir>
#include <QDoubleSpinBox>
#include <QElapsedTimer>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QImageReader>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QScrollArea>
#include <QSpinBox>
#include <QSplitter>
#include <QCloseEvent>
#include <QThread>
#include <QVBoxLayout>
#include <QTime>
#include <functional>

#include "core/rip_engine.h"
#include "gui/previewrenderer.h"

namespace mtr {
namespace gui {

namespace {

// 后台 RIP 线程
class RipThread : public QThread
{
public:
    RipThread(mtr::RipJob job, QObject *parent = nullptr)
        : QThread(parent), m_job(std::move(job)) {}
    bool ok = false;
    QString err;
    qint64 elapsedMs = 0;

protected:
    void run() override
    {
        QElapsedTimer t;
        t.start();
        mtr::RipEngine engine;
        ok = engine.run(m_job, &err);
        elapsedMs = t.elapsed();
    }

private:
    mtr::RipJob m_job;
};

// 后台预览线程：解码 PRN + 渲染（避免大图卡住 GUI）
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

QString modeLabel(const mtr::PrsMode &m)
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
}

} // namespace

MainWindow::MainWindow(QWidget *parent) : QMainWindow(parent)
{
    setWindowTitle(QStringLiteral("mtr RIP Studio — 蒙泰替代 RIP（C++/Qt 自研）"));
    resize(1280, 860);
    buildUi();
    log(QStringLiteral("就绪。资源目录: %1").arg(QCoreApplication::applicationDirPath()));
}

MainWindow::~MainWindow()
{
    for (QThread *th : {m_thread, m_previewThread}) {
        if (th && th->isRunning()) {
            th->requestInterruption();
            th->wait(3000);
        }
    }
}

void MainWindow::buildUi()
{
    auto *central = new QWidget(this);
    auto *root = new QVBoxLayout(central);
    setCentralWidget(central);

    // ---- 顶部：文件与模式 ----
    auto *fileBox = new QGroupBox(QStringLiteral("作业"), central);
    auto *form = new QFormLayout(fileBox);
    form->setLabelAlignment(Qt::AlignRight);

    auto *inputRow = new QWidget(fileBox);
    auto *inputLay = new QHBoxLayout(inputRow);
    inputLay->setContentsMargins(0, 0, 0, 0);
    m_inputEdit = new QLineEdit(inputRow);
    m_inputEdit->setPlaceholderText(QStringLiteral("输入图像：PNG / JPEG / TIFF（几何按 PNG 内嵌 DPI）"));
    auto *inputBtn = new QPushButton(QStringLiteral("浏览…"), inputRow);
    inputLay->addWidget(m_inputEdit, 1);
    inputLay->addWidget(inputBtn);
    form->addRow(QStringLiteral("输入图像"), inputRow);

    auto *prsRow = new QWidget(fileBox);
    auto *prsLay = new QHBoxLayout(prsRow);
    prsLay->setContentsMargins(0, 0, 0, 0);
    m_prsCombo = new QComboBox(prsRow);
    m_prsCombo->setEditable(false);
    auto *prsBtn = new QPushButton(QStringLiteral("浏览…"), prsRow);
    prsLay->addWidget(m_prsCombo, 1);
    prsLay->addWidget(prsBtn);
    form->addRow(QStringLiteral("打印设置 .prs"), prsRow);

    m_modeCombo = new QComboBox(fileBox);
    form->addRow(QStringLiteral("模式 modeId"), m_modeCombo);

    auto *outRow = new QWidget(fileBox);
    auto *outLay = new QHBoxLayout(outRow);
    outLay->setContentsMargins(0, 0, 0, 0);
    m_outputEdit = new QLineEdit(outRow);
    m_outputEdit->setPlaceholderText(QStringLiteral("输出 .prn 路径（默认与输入图同目录）"));
    auto *outBtn = new QPushButton(QStringLiteral("浏览…"), outRow);
    outLay->addWidget(m_outputEdit, 1);
    outLay->addWidget(outBtn);
    form->addRow(QStringLiteral("输出 PRN"), outRow);

    root->addWidget(fileBox);

    // ---- 中部：参数 + 预览 ----
    auto *splitter = new QSplitter(Qt::Horizontal, central);

    auto *optBox = new QGroupBox(QStringLiteral("参数"), splitter);
    auto *optForm = new QFormLayout(optBox);

    m_rotateCombo = new QComboBox(optBox);
    m_rotateCombo->addItem(QStringLiteral("0°"), 0);
    m_rotateCombo->addItem(QStringLiteral("180°（镜像）"), 180);
    optForm->addRow(QStringLiteral("旋转"), m_rotateCombo);

    auto *scaleRow = new QWidget(optBox);
    auto *scaleLay = new QHBoxLayout(scaleRow);
    scaleLay->setContentsMargins(0, 0, 0, 0);
    m_scaleX = new QDoubleSpinBox(scaleRow);
    m_scaleY = new QDoubleSpinBox(scaleRow);
    for (auto *s : {m_scaleX, m_scaleY}) {
        s->setRange(0.01, 100.0);
        s->setDecimals(3);
        s->setValue(1.0);
        s->setSingleStep(0.1);
    }
    scaleLay->addWidget(new QLabel(QStringLiteral("X"), scaleRow));
    scaleLay->addWidget(m_scaleX);
    scaleLay->addWidget(new QLabel(QStringLiteral("Y"), scaleRow));
    scaleLay->addWidget(m_scaleY);
    optForm->addRow(QStringLiteral("缩放"), scaleRow);

    auto *marginRow = new QWidget(optBox);
    auto *marginLay = new QHBoxLayout(marginRow);
    marginLay->setContentsMargins(0, 0, 0, 0);
    m_marginL = new QSpinBox(marginRow);
    m_marginT = new QSpinBox(marginRow);
    m_marginR = new QSpinBox(marginRow);
    m_marginB = new QSpinBox(marginRow);
    for (auto *s : {m_marginL, m_marginT, m_marginR, m_marginB})
        s->setRange(-10000, 10000);
    marginLay->addWidget(new QLabel(QStringLiteral("L"), marginRow));
    marginLay->addWidget(m_marginL);
    marginLay->addWidget(new QLabel(QStringLiteral("T"), marginRow));
    marginLay->addWidget(m_marginT);
    marginLay->addWidget(new QLabel(QStringLiteral("R"), marginRow));
    marginLay->addWidget(m_marginR);
    marginLay->addWidget(new QLabel(QStringLiteral("B"), marginRow));
    marginLay->addWidget(m_marginB);
    optForm->addRow(QStringLiteral("页边距"), marginRow);

    m_whiteCombo = new QComboBox(optBox);
    m_whiteCombo->addItem(QStringLiteral("不打印白墨"), 0);
    m_whiteCombo->addItem(QStringLiteral("W1 full（满版）"), 1);
    m_whiteCombo->addItem(QStringLiteral("W1 color（按彩色区域）"), 2);
    optForm->addRow(QStringLiteral("白墨"), m_whiteCombo);

    m_inkModeCombo = new QComboBox(optBox);
    m_inkModeCombo->addItem(QStringLiteral("invaginate"), 0);
    m_inkModeCombo->addItem(QStringLiteral("expand"), 1);
    optForm->addRow(QStringLiteral("inkIE 模式"), m_inkModeCombo);

    auto *dotRow = new QWidget(optBox);
    auto *dotLay = new QHBoxLayout(dotRow);
    dotLay->setContentsMargins(0, 0, 0, 0);
    m_dotL = new QSpinBox(dotRow);
    m_dotT = new QSpinBox(dotRow);
    m_dotR = new QSpinBox(dotRow);
    m_dotB = new QSpinBox(dotRow);
    for (auto *s : {m_dotL, m_dotT, m_dotR, m_dotB})
        s->setRange(0, 1000);
    dotLay->addWidget(new QLabel(QStringLiteral("L"), dotRow));
    dotLay->addWidget(m_dotL);
    dotLay->addWidget(new QLabel(QStringLiteral("T"), dotRow));
    dotLay->addWidget(m_dotT);
    dotLay->addWidget(new QLabel(QStringLiteral("R"), dotRow));
    dotLay->addWidget(m_dotR);
    dotLay->addWidget(new QLabel(QStringLiteral("B"), dotRow));
    dotLay->addWidget(m_dotB);
    optForm->addRow(QStringLiteral("inkIE 边距"), dotRow);

    // 引擎当前实现范围：rotate 180 / 白墨 / mode 已生效；scale、margin、inkIE 为预留参数
    for (QWidget *w : {static_cast<QWidget *>(m_scaleX), static_cast<QWidget *>(m_scaleY),
                       static_cast<QWidget *>(m_marginL), static_cast<QWidget *>(m_marginT),
                       static_cast<QWidget *>(m_marginR), static_cast<QWidget *>(m_marginB),
                       static_cast<QWidget *>(m_inkModeCombo), static_cast<QWidget *>(m_dotL),
                       static_cast<QWidget *>(m_dotT), static_cast<QWidget *>(m_dotR),
                       static_cast<QWidget *>(m_dotB)}) {
        w->setEnabled(false);
        w->setToolTip(QStringLiteral("预留参数：当前引擎未实现（蒙泰参数已解析，待后续版本）"));
    }

    m_generateBtn = new QPushButton(QStringLiteral("▶ RIP 生成 PRN"), optBox);
    m_generateBtn->setMinimumHeight(36);
    optForm->addRow(m_generateBtn);
    m_previewBtn = new QPushButton(QStringLiteral("👁 预览页面"), optBox);
    optForm->addRow(m_previewBtn);

    optForm->addRow(new QLabel(QStringLiteral("预览通道"), optBox));
    m_channelCombo = new QComboBox(optBox);
    m_channelCombo->addItem(QStringLiteral("合成（模拟打印）"), QStringLiteral("__composite__"));
    m_channelCombo->addItem(QStringLiteral("原图"), QStringLiteral("__original__"));
    optForm->addRow(m_channelCombo);

    splitter->addWidget(optBox);
    auto *optScroll = new QScrollArea(splitter);
    optScroll->setWidget(optBox);
    optScroll->setWidgetResizable(true);
    splitter->addWidget(optScroll);

    auto *previewBox = new QGroupBox(QStringLiteral("打印点阵预览"), splitter);
    auto *previewLay = new QVBoxLayout(previewBox);
    m_previewLabel = new QLabel(previewBox);
    m_previewLabel->setAlignment(Qt::AlignCenter);
    m_previewLabel->setMinimumSize(400, 300);
    m_previewLabel->setStyleSheet(QStringLiteral("background:#2b2b2b; color:#ccc;"));
    m_previewLabel->setText(QStringLiteral("生成 PRN 后点击「预览页面」"));
    auto *previewScroll = new QScrollArea(previewBox);
    previewScroll->setWidget(m_previewLabel);
    previewScroll->setWidgetResizable(true);
    previewLay->addWidget(previewScroll, 1);
    m_infoLabel = new QLabel(QStringLiteral("—"), previewBox);
    m_infoLabel->setWordWrap(true);
    previewLay->addWidget(m_infoLabel);
    splitter->addWidget(previewBox);
    splitter->setStretchFactor(0, 0);
    splitter->setStretchFactor(1, 1);
    splitter->setSizes({360, 900});

    root->addWidget(splitter, 1);

    // ---- 底部：日志 ----
    m_log = new QPlainTextEdit(central);
    m_log->setReadOnly(true);
    m_log->setMaximumBlockCount(2000);
    m_log->setMinimumHeight(120);
    root->addWidget(m_log);

    // 连接
    connect(inputBtn, &QPushButton::clicked, this, &MainWindow::onBrowseInput);
    connect(prsBtn, &QPushButton::clicked, this, &MainWindow::onBrowsePrs);
    connect(outBtn, &QPushButton::clicked, this, &MainWindow::onBrowseOutput);
    connect(m_prsCombo, &QComboBox::currentIndexChanged, this, &MainWindow::onLoadPrs);
    connect(m_modeCombo, &QComboBox::currentIndexChanged, this, &MainWindow::onModeChanged);
    connect(m_generateBtn, &QPushButton::clicked, this, &MainWindow::onGenerate);
    connect(m_previewBtn, &QPushButton::clicked, this, &MainWindow::onPreview);
    connect(m_channelCombo, &QComboBox::currentIndexChanged, this, &MainWindow::onChannelChanged);
    connect(m_inputEdit, &QLineEdit::editingFinished, this, [this] {
        const QString p = m_inputEdit->text().trimmed();
        if (p.isEmpty()) return;
        if (m_outputEdit->text().trimmed().isEmpty()) {
            QFileInfo fi(p);
            m_outputEdit->setText(fi.absolutePath() + QLatin1Char('/') +
                                  fi.completeBaseName() + QStringLiteral(".prn"));
        }
        loadInputImageInto(p, &m_original, [this](const QString &m) { log(m); });
        if (!m_original.isNull())
            m_originalPreview = m_original.scaled(1600, 1600, Qt::KeepAspectRatio,
                                                  Qt::SmoothTransformation);
    });

    // 发现 .prs
    const QStringList searchDirs = {
        QCoreApplication::applicationDirPath() + QStringLiteral("/prs"),
        QCoreApplication::applicationDirPath() + QStringLiteral("/../reference/prs"),
        QDir::currentPath() + QStringLiteral("/reference/prs"),
    };
    for (const QString &dir : searchDirs) {
        QDir d(dir);
        if (!d.exists()) continue;
        for (const QFileInfo &fi : d.entryInfoList({QStringLiteral("*.prs")}, QDir::Files)) {
            if (m_prsCombo->findText(fi.absoluteFilePath()) < 0)
                m_prsCombo->addItem(fi.absoluteFilePath());
        }
    }
    if (m_prsCombo->count() == 0)
        m_prsCombo->addItem(QStringLiteral("（未找到 .prs，请手动浏览）"));
    onLoadPrs();
}

void MainWindow::autoLoad(const QString &input, const QString &prs, int modeId,
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

void MainWindow::log(const QString &msg)
{
    if (!m_log) return;
    m_log->appendPlainText(QStringLiteral("[%1] %2")
                               .arg(QTime::currentTime().toString(QStringLiteral("HH:mm:ss")), msg));
}

void MainWindow::onBrowseInput()
{
    const QString p = QFileDialog::getOpenFileName(
        this, QStringLiteral("选择输入图像"), QString(),
        QStringLiteral("图像 (*.png *.jpg *.jpeg *.tif *.tiff *.bmp);;所有文件 (*.*)"));
    if (p.isEmpty()) return;
    m_inputEdit->setText(p);
    if (m_outputEdit->text().trimmed().isEmpty()) {
        QFileInfo fi(p);
        m_outputEdit->setText(fi.absolutePath() + QLatin1Char('/') +
                              fi.completeBaseName() + QStringLiteral(".prn"));
    }
    loadInputImageInto(p, &m_original, [this](const QString &m) { log(m); });
    if (!m_original.isNull())
        m_originalPreview = m_original.scaled(1600, 1600, Qt::KeepAspectRatio,
                                              Qt::SmoothTransformation);
}

void MainWindow::onBrowsePrs()
{
    const QString p = QFileDialog::getOpenFileName(
        this, QStringLiteral("选择打印设置 .prs"), QString(),
        QStringLiteral("打印设置 (*.prs);;所有文件 (*.*)"));
    if (p.isEmpty()) return;
    m_prsCombo->addItem(p);
    m_prsCombo->setCurrentIndex(m_prsCombo->count() - 1);
    onLoadPrs();
}

void MainWindow::onBrowseOutput()
{
    const QString p = QFileDialog::getSaveFileName(
        this, QStringLiteral("输出 PRN"), m_outputEdit->text(),
        QStringLiteral("PRN (*.prn);;所有文件 (*.*)"));
    if (!p.isEmpty()) m_outputEdit->setText(p);
}

void MainWindow::onLoadPrs()
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
    m_modeCombo->blockSignals(true);
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
    m_modeCombo->blockSignals(false);
    m_modeCombo->setCurrentIndex(idx);
    onModeChanged();
}

void MainWindow::onModeChanged()
{
    const int id = m_modeCombo->currentData().toInt();
    const mtr::PrsMode *m = m_prs.mode(id);
    if (!m) {
        m_hasMode = false;
        return;
    }
    m_mode = *m;
    m_hasMode = true;
    static QString lastModeLabel;
    const QString lbl = modeLabel(m_mode);
    if (lastModeLabel != lbl) {
        lastModeLabel = lbl;
        log(QStringLiteral("当前模式: %1").arg(lbl));
    }
}

bool MainWindow::collectJob(mtr::RipJob *job, QString *err)
{
    if (!m_hasMode) {
        if (err) *err = QStringLiteral("请先加载 .prs 并选择模式");
        return false;
    }
    const QString input = m_inputEdit->text().trimmed();
    if (input.isEmpty() || !QFileInfo::exists(input)) {
        if (err) *err = QStringLiteral("输入图像不存在");
        return false;
    }
    const QString output = m_outputEdit->text().trimmed();
    if (output.isEmpty()) {
        if (err) *err = QStringLiteral("请指定输出 PRN 路径");
        return false;
    }
    job->inputPath = input;
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
    job->inputColorEditor.clear();
    if (m_whiteCombo->currentData().toInt() > 0) {
        mtr::WhiteInkSpec w;
        w.inkName = QStringLiteral("W1");
        w.mode = m_whiteCombo->currentData().toInt() == 1 ? QStringLiteral("full")
                                                          : QStringLiteral("color");
        job->inputColorEditor.append(w);
    }
    return true;
}

void MainWindow::onGenerate()
{
    if (m_thread && m_thread->isRunning()) return;
    mtr::RipJob job;
    QString err;
    if (!collectJob(&job, &err)) {
        QMessageBox::warning(this, QStringLiteral("参数不完整"), err);
        return;
    }
    m_lastPrn = job.prnPath;
    setBusy(true);
    log(QStringLiteral("RIP 开始：%1（mode %2）→ %3")
            .arg(QFileInfo(job.inputPath).fileName()).arg(job.modeId).arg(job.prnPath));
    auto *th = new RipThread(job, this);
    m_thread = th;
    connect(th, &QThread::finished, this, &MainWindow::onThreadFinished);
    th->start();
}

void MainWindow::onThreadFinished()
{
    auto *th = static_cast<RipThread *>(m_thread);
    const bool ok = th ? th->ok : false;
    const QString err = th ? th->err : QStringLiteral("内部错误");
    const qint64 ms = th ? th->elapsedMs : 0;
    if (th) th->deleteLater();
    m_thread = nullptr;
    setBusy(false);
    if (!ok) {
        log(QStringLiteral("RIP 失败: %1").arg(err));
        QMessageBox::critical(this, QStringLiteral("RIP 失败"), err);
        return;
    }
    const qint64 size = QFileInfo(m_lastPrn).size();
    log(QStringLiteral("RIP 完成：%1 ms，输出 %2 字节").arg(ms).arg(size));
    updatePreview();
}

void MainWindow::onPreview()
{
    if (m_lastPrn.isEmpty() || !QFileInfo::exists(m_lastPrn)) {
        QMessageBox::information(this, QStringLiteral("提示"),
                                 QStringLiteral("请先生成 PRN（或填写已存在的 PRN 路径后点『预览页面』）"));
        const QString p = m_outputEdit->text().trimmed();
        if (!p.isEmpty() && QFileInfo::exists(p)) m_lastPrn = p;
        else return;
    }
    updatePreview();
}

void MainWindow::updatePreview()
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
}

void MainWindow::onChannelChanged(int)
{
    fitPreview();
}

void MainWindow::fitPreview()
{
    const QString key = m_channelCombo->currentData().toString();
    QImage img;
    if (key == QLatin1String("__original__")) img = m_originalPreview;
    else if (key == QLatin1String("__composite__")) img = m_composite;
    else img = m_channels.value(key);
    if (img.isNull()) {
        m_previewLabel->setText(QStringLiteral("（该视图无数据）"));
        return;
    }
    // 适配显示区域（留 8px 边）
    QSize target = m_previewLabel->parentWidget() ? m_previewLabel->parentWidget()->size() : QSize(900, 700);
    target -= QSize(16, 16);
    if (target.width() < 120) target = QSize(900, 700);
    const QPixmap pm = QPixmap::fromImage(img).scaled(
        target, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    m_previewLabel->setPixmap(pm);
}

void MainWindow::resizeEvent(QResizeEvent *e)
{
    QMainWindow::resizeEvent(e);
    fitPreview();
}

void MainWindow::closeEvent(QCloseEvent *e)
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

void MainWindow::setBusy(bool busy)
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
}

} // namespace gui
} // namespace mtr
