#include "core/debug/prn_decode.h"

#include <QFile>

namespace mtr {

// TODO(T2): 完整的 ESC/P2 解析在 docs/prn_escp2.md 定稿后实现；
// 这里先留出接口，避免 CLI decode 无法链接。
bool PrnDecoder::decodeEscp2(const QString &prnPath, PrnImage *image, QString *err)
{
    Q_UNUSED(image);
    if (!QFile::exists(prnPath)) {
        if (err) *err = QStringLiteral("prn not found: %1").arg(prnPath);
        return false;
    }
    if (err) *err = QStringLiteral("prn decode not implemented yet (waiting for T2 spec)");
    return false;
}

bool PrnDecoder::decodeToDir(const QString &prnPath, const QString &outDir, QString *err)
{
    Q_UNUSED(outDir);
    return decodeEscp2(prnPath, nullptr, err);
}

} // namespace mtr
