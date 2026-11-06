// ============================================================================
// plane_pack.h —— 设备通道 2bit 点阵打包
// 每像素 1 字节(0..3) → 每字节 4 像素的打包行；行尾按 PRN 格式要求补齐。
// ============================================================================
#pragma once

#include <QVector>
#include <cstdint>

namespace mtr {

// 把 2bit 值(0..3)按“高位在前”打包：像素 x 放在字节 x/4 的 bit (6 - 2*(x%4))
// bytesPerLine = ceil(width/4)，再按 alignBytes 对齐补齐（0 表示不补齐）。
QVector<uint8_t> pack2BitRows(const QVector<uint8_t> &plane, int width, int height,
                              int *bytesPerLine, int alignBytes = 4);

// 1bit 打包（HSSF 某些模式用）
QVector<uint8_t> pack1BitRows(const QVector<uint8_t> &plane, int width, int height,
                              int *bytesPerLine, int alignBytes = 4);

} // namespace mtr
