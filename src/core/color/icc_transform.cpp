#include "core/color/icc_transform.h"

#include <QFile>

// lcms2 由 3rdparty/lcms2 提供（或系统库）；头文件通过 CMake include 路径引入。
#include <lcms2.h>

namespace mtr {

IccTransform::~IccTransform()
{
    if (m_handle)
        cmsDeleteTransform(static_cast<cmsHTRANSFORM>(m_handle));
}

namespace {

cmsHPROFILE openProfile(const QByteArray &data)
{
    if (data.isEmpty())
        return nullptr;
    return cmsOpenProfileFromMem(data.constData(), static_cast<cmsUInt32Number>(data.size()));
}

} // namespace

bool IccTransform::createRgbToCmyk(const QByteArray &srcProfile, const QByteArray &dstProfile,
                                   QString *err)
{
    cmsHPROFILE src = openProfile(srcProfile);
    cmsHPROFILE dst = openProfile(dstProfile);
    if (!src || !dst) {
        if (src) cmsCloseProfile(src);
        if (dst) cmsCloseProfile(dst);
        if (err) *err = QStringLiteral("icc: cannot open profiles");
        return false;
    }
    cmsHTRANSFORM h = cmsCreateTransform(src, TYPE_RGB_8, dst, TYPE_CMYK_8,
                                         INTENT_PERCEPTUAL, 0);
    cmsCloseProfile(src);
    cmsCloseProfile(dst);
    if (!h) {
        if (err) *err = QStringLiteral("icc: cmsCreateTransform failed");
        return false;
    }
    if (m_handle)
        cmsDeleteTransform(static_cast<cmsHTRANSFORM>(m_handle));
    m_handle = h;
    return true;
}

bool IccTransform::createCmykToCmyk(const QByteArray &srcProfile, const QByteArray &dstProfile,
                                    QString *err)
{
    cmsHPROFILE src = openProfile(srcProfile);
    cmsHPROFILE dst = openProfile(dstProfile);
    if (!src || !dst) {
        if (src) cmsCloseProfile(src);
        if (dst) cmsCloseProfile(dst);
        if (err) *err = QStringLiteral("icc: cannot open profiles");
        return false;
    }
    cmsHTRANSFORM h = cmsCreateTransform(src, TYPE_CMYK_8, dst, TYPE_CMYK_8,
                                         INTENT_PERCEPTUAL, 0);
    cmsCloseProfile(src);
    cmsCloseProfile(dst);
    if (!h) {
        if (err) *err = QStringLiteral("icc: cmsCreateTransform failed");
        return false;
    }
    if (m_handle)
        cmsDeleteTransform(static_cast<cmsHTRANSFORM>(m_handle));
    m_handle = h;
    return true;
}

bool IccTransform::transform(const unsigned char *in, unsigned char *out,
                             int inChannels, int outChannels)
{
    Q_UNUSED(inChannels);
    Q_UNUSED(outChannels);
    if (!m_handle)
        return false;
    cmsDoTransform(static_cast<cmsHTRANSFORM>(m_handle), in, out, 1);
    return true;
}

} // namespace mtr
