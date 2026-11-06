// ============================================================================
// icc_transform.h —— lcms2 封装：色彩空间转换（RGB→CMYK、CMYK→设备色）
// ============================================================================
#pragma once

#include <QByteArray>
#include <QString>

namespace mtr {

class IccTransform {
public:
    ~IccTransform();

    // 从内存/文件加载 profile 并建立转换
    bool createRgbToCmyk(const QByteArray &srcProfile, const QByteArray &dstProfile, QString *err);
    bool createCmykToCmyk(const QByteArray &srcProfile, const QByteArray &dstProfile, QString *err);
    bool isReady() const { return m_handle != nullptr; }

    // 单像素转换（8bit）。inChannels/outChannels 必须与 profile 匹配。
    bool transform(const unsigned char *in, unsigned char *out, int inChannels, int outChannels);

private:
    void *m_handle = nullptr;
};

} // namespace mtr
