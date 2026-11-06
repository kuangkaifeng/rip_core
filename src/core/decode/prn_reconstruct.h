// ============================================================================
// prn_reconstruct.h —— ESC/P2 PRN 反解（蒙泰 A3-DTF-1390）
//
// 把任意 ESC/P2 .prn（作业头 + 命令区 + 光栅块 + 尾部）解析回"页面点阵"：
//   * 每墨色一张 8bit 平面（0..3 点大小，页面坐标：page_row = pos + rowStep*r - off）
//   * 结构信息（块位置/推进/记录 n,m/颜色顺序/命令区参数）
//   * 从 PRN 还原"内容平面"（contentW x contentH，按记录顺序），用于重编码对比
//
// 几何依据见 layout_escp2.h。
// ============================================================================
#pragma once

#include <QByteArray>
#include <QImage>
#include <QMap>
#include <QString>
#include <QStringList>
#include <QVector>
#include <cstdint>

#include "core/encode/escp2_writer.h"

namespace mtr {

struct Escp2RecordInfo {
    int block = 0;
    int color = 0;
    int comp = 1;
    int depth = 2;
    int n = 0;
    int m = 0;
    uint32_t dollar = 0;
    int dataOffset = 0;   // RLE 数据起点（文件偏移）
    int dataLen = 0;      // 压缩数据长度
};

struct Escp2JobInfo {
    // ---- 命令区 ----
    int unit = 2880;
    int uA = 4, uV = 4, uH = 4;
    int pageUnit = 720;
    int rasterR = 1440, rasterV = 16, rasterH = 2;
    int rasterVDpi = 90, rasterHDpi = 720;
    int pageFormatA = 0, pageFormatB = 0;   // ESC(c) 两个 int32
    int pageMargin = 0;                     // = -pageFormatA
    quint32 paperWidth = 0, paperHeight = 0; // ESC(S)
    int colorMode = 2;
    int dotSize = 0;

    // ---- 远程头 ----
    QByteArray ti;       // 原始 TI 数据
    QByteArray js;       // 原始 JS 数据
    QByteArray jh;       // 原始 JH 数据
    bool hasTi = false, hasJs = false, hasJh = false;

    // ---- 结构 ----
    int modeIdGuess = -1;
    int rowStep = 8;
    int planes = 0;
    QVector<int> colorOrder;
    QVector<int> recordOffsets;
    int initialPos = 0;                  // 首块前 ESC(v 累计
    QVector<int> positions;              // 每块位置 pos[k]
    QVector<int> advances;               // 每块前 ESC(v（block0 为 initialPos 特例）
    QVector<Escp2RecordInfo> records;    // 全部记录（按文件顺序）
    QVector<int> blockRecordStart;       // 每块首记录的 records 下标
    QVector<QByteArray> rawData;         // 每条记录解码后的 n*m 字节（2bit 打包）

    // ---- 推导 ----
    int p0 = 0;
    int contentWidthDots = 0;
    int contentHeightDots = 0;
    int pageRows = 0;
    int maxWidthDots = 0;
    bool decoded = false;

    QStringList warnings;
};

struct PrnPageRaster {
    int rows = 0;
    int widthDots = 0;
    QVector<int> colors;
    QMap<int, QVector<uint8_t>> planes;    // 页面坐标 0..3（多块取 max）
    QVector<uint8_t> inkUnion;             // 所有颜色 max
    int overlapPixels = 0;                 // 被多块写入的像素数
    int conflictPixels = 0;                // 被多块写入且都非 0 的像素数
};

// ESC/P2 RLE
QByteArray rleDecodeBytes(const QByteArray &data, int offset, int expected, int *consumed);

class PrnReconstructor {
public:
    // 仅解析结构（+解码所有记录数据）
    static bool parse(const QString &prnPath, Escp2JobInfo *job, QString *err);

    // 解析并铺回页面 raster；modeIdOverride<0 时自动识别
    static bool decode(const QString &prnPath, PrnPageRaster *page, Escp2JobInfo *job,
                       QString *err, int modeIdOverride = -1);

    // 还原"内容平面"：planes[record] = contentW*contentH（0..3）
    static bool extractContentPlanes(const QString &prnPath, int modeId,
                                     QVector<QVector<uint8_t>> *planes,
                                     int *widthDots, int *heightDots,
                                     Escp2JobInfo *job, QString *err);

    // 导出每色 BMP（灰阶：level 0..3 -> 255..0）+ inkUnion
    static bool exportBmps(const PrnPageRaster &page, const QString &outDir, QString *err);

    static QImage planeToImage(const QVector<uint8_t> &plane, int width, int height);

    // 由作业头信息构造 Escp2Config（作业名/主机名/时间）
    static Escp2Config jobInfoToConfig(const Escp2JobInfo &job);
};

} // namespace mtr
