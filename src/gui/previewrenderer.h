// ============================================================================
// previewrenderer.h —— PRN 打印点阵预览渲染（GUI 用）
//
// 把生成的 .prn 解码回页面点阵，渲染成"模拟打印效果"的 QImage：
//   * ESC/P2（改装机）：用 PrnReconstructor 反解
//   * HSSF 0x5555（板卡机）：按 48B 头 + 行交错平面手动解码
// 合成规则（近似减色）：R = 255*(1-Cc)*(1-Kc), G = 255*(1-Mc)*(1-Kc), B = 255*(1-Yc)*(1-Kc)
// 渲染按目标分辨率采样，不生成全尺寸图像；大图（>40M 像素）跳过预览并返回提示。
// ============================================================================
#pragma once

#include <QImage>
#include <QMap>
#include <QSize>
#include <QString>
#include <QVector>
#include <cstdint>

namespace mtr {
namespace gui {

struct PreviewData {
    bool ok = false;
    QString note;
    int widthDots = 0;
    int heightDots = 0;
    QImage composite;                       // 合成彩色预览
    QMap<QString, QImage> channels;         // 单通道灰度（level 0..3 -> 亮度）
    QImage original;                        // 原图（缩放后）
    QString format;                         // "ESC/P2" / "HSSF"
};

// original: 输入图（可为空）；modeIdOverride<0 时由解码器推断
// maxSide: 预览图像最长边（默认 1600）；渲染按此尺寸采样，避免大图卡顿
bool renderPrnPreview(const QString &prnPath, const QImage &original,
                      PreviewData *out, QString *err, int modeIdOverride = -1,
                      int maxSide = 1600);

// 单通道 level 平面 -> 该墨水颜色的可视化（按最长边采样）
QImage renderChannelScaled(const QVector<uint8_t> &levels, int w, int h,
                           const QString &ink, int maxSide);
QImage renderChannel(const QVector<uint8_t> &levels, int w, int h, const QString &ink);

// 多通道 level 平面 -> 合成彩色预览（按最长边采样）
QImage composeInksScaled(const QMap<QString, QVector<uint8_t>> &planes, int w, int h,
                         int maxSide);
QImage composeInks(const QMap<QString, QVector<uint8_t>> &planes, int w, int h);

} // namespace gui
} // namespace mtr
