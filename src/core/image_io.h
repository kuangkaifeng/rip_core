// ============================================================================
// image_io.h —— 图像加载（Qt QImage，覆盖 rip-studio 合成后的 PNG/JPEG/TIFF）
// ============================================================================
#pragma once

#include <QImage>
#include <QString>

namespace mtr {
namespace image {

// 加载为标准 RGBA8888；TIFF/PNG/JPEG/BMP 均可（走 Qt 插件）。
bool loadRgba(const QString &path, QImage *out, QString *err);

// 按蒙泰实测语义解析输入图像 DPI：
//   PNG：pHYs（unit=1）-> dpi；无 pHYs -> 72
//   JPEG：JFIF unit=1 -> xdensity；unit=2 -> xdensity*2.54；unit=0/无 JFIF -> 72
//   其它：Qt dpm>0 -> dpi；否则 72
// （oracle 实测：860x564 无有效 DPI 的 JPEG 按 72dpi 处理 -> 内容 8600x5640）
int resolveImageDpi(const QString &path, const QImage &img);

// 保存 BMP（验证预览用）
bool saveBmp(const QImage &img, const QString &path, QString *err);

} // namespace image
} // namespace mtr
