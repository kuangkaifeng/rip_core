#include "core/encode/hssf_writer.h"

#include <cstring>
#include <vector>
#include <cmath>

namespace mtr {

namespace {

inline void put32(std::vector<uint8_t> &v, uint32_t x)
{
    v.push_back(static_cast<uint8_t>(x & 0xFF));
    v.push_back(static_cast<uint8_t>((x >> 8) & 0xFF));
    v.push_back(static_cast<uint8_t>((x >> 16) & 0xFF));
    v.push_back(static_cast<uint8_t>((x >> 24) & 0xFF));
}

// 2bit MSB-first 打包一行：像素 x -> 字节 x/4, bit 6-2*(x%4)
void pack2BitRow(const uint8_t *row, int width, uint8_t *dst, int bpl)
{
    std::memset(dst, 0, static_cast<size_t>(bpl));
    for (int x = 0; x < width; ++x) {
        const uint8_t v = row[x] & 0x03;
        dst[x >> 2] |= static_cast<uint8_t>(v << (6 - 2 * (x & 3)));
    }
}

} // namespace

HssfWriter::HssfWriter(const HssfConfig &cfg) : m_cfg(cfg)
{
    if (m_cfg.planeOrder.isEmpty())
        m_cfg.planeOrder = {0, 1, 2, 3, 4}; // K,C,M,Y,W1（索引到 planes）
}

int HssfWriter::bytesPerLine(int width)
{
    // align8(ceil(W*2bit/8)) = align8(ceil(W/4))
    int bpl = (width + 3) / 4;
    bpl = ((bpl + 7) / 8) * 8;
    return bpl;
}

uint32_t HssfWriter::paperWidthBits(int widthPx, uint32_t xDPI)
{
    // paperWidth = float32(W / xDPI * 0.0254)，单位米，按 float 位模式存放
    const float meters = static_cast<float>(static_cast<double>(widthPx) /
                                            static_cast<double>(xDPI > 0 ? xDPI : 720) * 0.0254);
    uint32_t bits = 0;
    std::memcpy(&bits, &meters, 4);
    return bits;
}

QByteArray HssfWriter::build(int width, int height,
                             const QVector<QVector<uint8_t>> &planes) const
{
    const int bpl = bytesPerLine(width);
    const int planeCount = static_cast<int>(m_cfg.colorPlane);

    std::vector<uint8_t> header;
    header.reserve(48);
    put32(header, 0x5555);
    put32(header, m_cfg.xDPI);
    put32(header, m_cfg.yDPI);
    put32(header, static_cast<uint32_t>(bpl));
    put32(header, static_cast<uint32_t>(height));
    put32(header, static_cast<uint32_t>(width));
    put32(header, paperWidthBits(width, m_cfg.xDPI));
    put32(header, static_cast<uint32_t>(planeCount));
    put32(header, static_cast<uint32_t>(m_cfg.dotBits));     // reserved[0] = 点位数
    put32(header, static_cast<uint32_t>(m_cfg.passCount));   // reserved[1] = pass 数
    put32(header, static_cast<uint32_t>(m_cfg.rowsPerStore));// reserved[2] = 每次存储行数
    put32(header, static_cast<uint32_t>(m_cfg.reserved3));   // reserved[3]

    QByteArray out;
    out.resize(static_cast<qsizetype>(48) +
               static_cast<qsizetype>(height) * planeCount * bpl);
    std::memcpy(out.data(), header.data(), 48);

    uint8_t *dst = reinterpret_cast<uint8_t *>(out.data()) + 48;
    std::vector<uint8_t> rowBuf(static_cast<size_t>(bpl));
    for (int y = 0; y < height; ++y) {
        for (int p = 0; p < planeCount; ++p) {
            const int pi = (p < m_cfg.planeOrder.size()) ? m_cfg.planeOrder[p] : p;
            const QVector<uint8_t> &plane = (pi < planes.size()) ? planes.at(pi) : QVector<uint8_t>();
            if (plane.size() >= static_cast<qsizetype>(width) * (y + 1))
                pack2BitRow(plane.constData() + static_cast<qsizetype>(y) * width, width,
                            rowBuf.data(), bpl);
            else
                std::memset(rowBuf.data(), 0, static_cast<size_t>(bpl));
            std::memcpy(dst, rowBuf.data(), static_cast<size_t>(bpl));
            dst += bpl;
        }
    }
    return out;
}

} // namespace mtr
