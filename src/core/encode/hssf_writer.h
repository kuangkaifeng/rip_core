// ============================================================================
// hssf_writer.h —— 汉森 HSSF 0x5555 PRN 写出器（板卡机 H13/XP600 路线）
//
// 依据 docs/prn_board.md（board-analyst 用 oracle + 真机样本验证过的规范）：
//   偏移 0x00 u32 signature = 0x5555
//   0x04 u32 xDPI（H13 mode0 = 720）
//   0x08 u32 yDPI（720/1080/1440/2160 随 modeId）
//   0x0C u32 bytesPerLine = align8(ceil(W*2/8)) = align8(ceil(W/4))
//   0x10 u32 height
//   0x14 u32 width
//   0x18 u32 paperWidth = float32(W / xDPI * 0.0254) 的位模式（单位：米）
//   0x1C u32 colorPlane（H13 = 5：K,C,M,Y,W1）
//   0x20 u32 reserved[4] 建议 [2, pass, 1, 0]
//   数据区：行交错（row-major），每行依次 5 个平面，每平面 bytesPerLine 字节；
//           2bit/像素 MSB-first（像素 x → 字节 x/4，bit 6-2*(x%4)），无分块/pass 头。
//   文件大小 = 48 + H * colorPlane * bytesPerLine
// ============================================================================
#pragma once

#include <QByteArray>
#include <QVector>
#include <cstdint>

namespace mtr {

struct HssfConfig {
    uint32_t xDPI = 720;
    uint32_t yDPI = 720;
    uint32_t colorPlane = 5;     // H13: K,C,M,Y,W1
    int dotBits = 2;
    int passCount = 1;
    int rowsPerStore = 1;
    int reserved3 = 0;
    // 平面顺序（默认 H13: K,C,M,Y,W1）
    QVector<int> planeOrder;     // 索引到 planes 数组
};

class HssfWriter {
public:
    explicit HssfWriter(const HssfConfig &cfg = HssfConfig());

    // planes: 每平面（按墨水语义顺序 K,C,M,Y,W1...）的 levels，尺寸 width*height，值 0..3
    QByteArray build(int width, int height, const QVector<QVector<uint8_t>> &planes) const;

    static int bytesPerLine(int width);
    static uint32_t paperWidthBits(int widthPx, uint32_t xDPI);

private:
    HssfConfig m_cfg;
};

} // namespace mtr
