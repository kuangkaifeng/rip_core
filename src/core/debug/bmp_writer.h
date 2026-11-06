// ============================================================================
// bmp_writer.h —— 无 Qt 插件依赖的 24bit BMP 写出（验证预览）
// ============================================================================
#pragma once

#include <QImage>
#include <QString>

namespace mtr {

bool writeBmp24(const QImage &image, const QString &path, QString *err);

} // namespace mtr
