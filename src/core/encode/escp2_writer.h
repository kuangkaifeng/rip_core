// ============================================================================
// escp2_writer.h —— EPSON ESC/P2 作业（.prn）写出器（改装机 A3-DTF-1390）
//
// 格式依据：蒙泰 test.prn / a.prn / bin/bin/temp/data/*.prn 与 USB 抓包，
// 详细规范见 docs/prn_escp2.md（T2 产出）。
// ============================================================================
#pragma once

#include <QByteArray>
#include <QVector>
#include <QDateTime>
#include <cstdint>

namespace mtr {

struct Escp2Color {
    uint8_t code;    // ESC i 的颜色代码（0x12/0x11/0x00/0x02/0x01/0x04 ...）
    QString name;    // 对应的设备通道名，便于调试
};

struct Escp2Config {
    // 作业头
    QByteArray jobName = "MAINTOPRINT";
    QByteArray hostName = "Maintop Host";
    QDateTime time;                 // TI 时间（为空则用当前时间）

    // 命令区参数（单位均为 ESC/P2 规定单位；实测见 docs/02_geometry_escp2.md）
    int uA = 4, uV = 4, uH = 4;     // ESC ( U 三个比值（2880/比值 = unit/in）
    int rasterR = 1440;             // ESC ( D
    int rasterV = 16;
    int rasterH = 2;
    uint8_t dotSize = 0x21;         // ESC ( e 的墨滴大小字节
    uint16_t colorMode = 2;         // ESC ( K 的 data[1]
    int paperWidth = 0;             // ESC ( S（page unit）
    int paperHeight = 0;
    int pageFormatTop = 0;          // ESC ( c 两个 int32
    int pageFormatBottom = 0;
    int dollarMode = 0;             // ESC ( $ 参数规则：0=恒 0；1=floor(block/16)%4
    int initialAdvance = 0;         // 首块前的 ESC ( v 初值（0=不写；金样本=150）
    uint8_t method = 0x41;          // ESC ( m 打印方法（m0..m3=0x41, m5/m7=0x40, m9=0x51）

    // 块参数
    int blockRows = 90;             // m
    int blockAdvance = 11;          // ESC ( v
    int bytesPerLine = 360;         // n
    int colorDepth = 2;             // ESC i 中位深
    QVector<Escp2Color> colors;     // 每块内颜色记录顺序
};

class Escp2Writer {
public:
    explicit Escp2Writer(const Escp2Config &cfg);

    void begin();
    // perColor[c] = bytesPerLine * blockRows 的已打包 2bit 行数据（可空=全 0）
    void addBlock(const QVector<QByteArray> &perColor);
    // advance >= 0 时用该值作为本块前的 ESC ( v（首块忽略）
    void addBlock(const QVector<QByteArray> &perColor, int advance);
    QByteArray finish();

    // RLE（按行独立；0..127 字面量，128..255 重复）
    static QByteArray rleEncode(const uint8_t *data, int len, int lineBytes);
    static QByteArray rleDecode(const uint8_t *data, int len, int expected);

private:
    void put(const void *p, int n);
    void putByte(uint8_t b);
    void putU16(uint16_t v);
    void putU32(uint32_t v);
    void putRemote(const char *cmd, const QByteArray &data);
    void writeJobHeader();
    void writePreamble();
    void writeTail();

    Escp2Config m_cfg;
    QByteArray m_out;
    int m_blockIndex = 0;
};

} // namespace mtr
