// ============================================================================
// mainwindow.h —— mtr RIP Studio 主窗口（Qt Widgets）
//
// 功能：选图 / 选 .prs / 选 mode / 设参数 → 调用自研 RIP 引擎生成 .prn
//       → 解码 PRN 显示"打印点阵预览"（合成色 / 单通道 / 原图）
// ============================================================================
#pragma once

#include <QMainWindow>
#include <QImage>
#include <QMap>
#include <QString>

#include "core/job_config.h"
#include "core/prs_config.h"

class QComboBox;
class QDoubleSpinBox;
class QLabel;
class QLineEdit;
class QPlainTextEdit;
class QPushButton;
class QSpinBox;
class QThread;
class QCloseEvent;

namespace mtr {
namespace gui {

class MainWindow : public QMainWindow
{
    Q_OBJECT
public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow() override;

    // 自动化（--screenshot / --selftest 用）：预填作业并立即生成
    void autoLoad(const QString &input, const QString &prs, int modeId, const QString &output = QString());
    void autoGenerate();

protected:
    void resizeEvent(QResizeEvent *e) override;
    void closeEvent(QCloseEvent *e) override;

private slots:
    void onLoadPrs();
    void onModeChanged();
    void onBrowseInput();
    void onBrowsePrs();
    void onBrowseOutput();
    void onGenerate();
    void onPreview();
    void onChannelChanged(int idx);
    void onThreadFinished();
    void onPreviewFinished();

private:
    void buildUi();
    void log(const QString &msg);
    void updatePreview();
    void applyPreview(class PreviewDataHolder *unused) = delete; // 占位（不使用）
    void fitPreview();
    bool collectJob(mtr::RipJob *job, QString *err);
    void setBusy(bool busy);

    // 控件
    QLineEdit *m_inputEdit = nullptr;
    QComboBox *m_prsCombo = nullptr;
    QComboBox *m_modeCombo = nullptr;
    QLineEdit *m_outputEdit = nullptr;
    QComboBox *m_rotateCombo = nullptr;
    QDoubleSpinBox *m_scaleX = nullptr;
    QDoubleSpinBox *m_scaleY = nullptr;
    QSpinBox *m_marginL = nullptr, *m_marginT = nullptr, *m_marginR = nullptr, *m_marginB = nullptr;
    QComboBox *m_whiteCombo = nullptr;
    QComboBox *m_inkModeCombo = nullptr;
    QSpinBox *m_dotL = nullptr, *m_dotT = nullptr, *m_dotR = nullptr, *m_dotB = nullptr;
    QPushButton *m_generateBtn = nullptr;
    QPushButton *m_previewBtn = nullptr;
    QComboBox *m_channelCombo = nullptr;
    QLabel *m_previewLabel = nullptr;
    QLabel *m_infoLabel = nullptr;
    QPlainTextEdit *m_log = nullptr;
    QThread *m_thread = nullptr;
    QThread *m_previewThread = nullptr;

    // 状态
    mtr::PrsConfig m_prs;
    QString m_prsPath;
    mtr::PrsMode m_mode;
    bool m_hasMode = false;
    QString m_lastPrn;
    QImage m_original;         // 原图（RIP 用，全尺寸）
    QImage m_originalPreview;  // 原图预览（缩到 <=1600）
    QMap<QString, QImage> m_channels;
    QImage m_composite;
};

} // namespace gui
} // namespace mtr
