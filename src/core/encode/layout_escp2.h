// ============================================================================
// layout_escp2.h —— ESC/P2 版面布局（蒙泰 A3-DTF-1390）
//
// 职责：把「内容页面点阵」（每墨色一张 8bit level 0..3 平面）按蒙泰实测几何
//       摆进 90 行一组的 raster 块，并交给 Escp2Writer 写成 .prn。
//
// 几何模型（依据 docs/prn_escp2.md，escp2-analyst 已逐字节验证）：
//   * 内容尺寸：content_w_dots = round(imgW * hdpi / imgDpi)
//               content_h_units= round(imgH * pageUnit / imgDpi)
//     （本模块输入已是该尺寸的平面：widthDots x heightDots）
//   * 纸行 p = pos[k] + VSTEP*r + recordOffset[rec]；VSTEP=mp.rowStep
//   * 内容行 i 对应纸行 P0 + i + recordOffset[rec]（P0 = 模式常量）
//   * 每个纸行只写进一个块：k = 满足 pos[k] ≡ p (mod VSTEP)、pos[k] ≤ p、
//     r=(p-pos[k])/VSTEP ≤ 89 的**最大** k（模逆直接算）。
//   * 块数 N = 1 + max k(p)
//   * n = align8(ceil(widthDots/4))；m = 90；每行独立 RLE
//   * 全零内容（纯白作业）：不发块，只在命令区后写一条 ESC(v（模式常量）再换页
//   * 背景：厂商在同一纸行被 k/k+8 两块覆盖时会做"羽化拆分"；我们默认让最大 k
//     独占该行（另一块写 0），打印结果等价。设置环境变量 **MTR_FEATHER=1** 后
//     启用可选羽化（仅 mode2）：较早块按实测密度表（r=79..89，90.8%→0）打印
//     部分 x 点、较晚块打印其余点；风险/说明见 layout_escp2.cpp 顶部注释。
//     默认关闭，不影响已验收的逐字节/逐点结果。
// ============================================================================
#pragma once

#include <QByteArray>
#include <QImage>
#include <QString>
#include <QVector>
#include <cstdint>

#include "core/encode/escp2_writer.h"

namespace mtr {

// A3-DTF-1390 各 modeId 的实测版面参数
struct Escp2ModeParams {
    int modeId = 2;
    int xDPI = 720;                // 内容水平分辨率（1 dot 对应 DPI）
    int yDPI = 720;                // 内容垂直分辨率（1 page unit 对应 DPI）
    int planes = 4;                // 墨水记录数
    int pageUnit = 720;            // ESC(U page unit（单位/英寸）
    int uA = 4, uV = 4, uH = 4;    // ESC(U 三个比值（2880 / 值 = dpi）
    int rasterR = 1440;            // ESC(D 参数
    int rasterV = 16;
    int rasterH = 2;
    int marginM = 555;             // ESC(c)/ESC(S) 的页边距常数（page unit）
    int advance = 79;              // 块推进（page unit，每块前 ESC(v）
    int rowStep = 8;               // VSTEP：块内相邻光栅行的纸行距（page unit）
    int blockRows = 90;            // m
    int baseP0 = 640;              // 内容起点纸行（模式常量）
    int initialAdvance = 0;        // 首块前 ESC(v（顶部空白跳过；生成可省略=0）
    int whiteAdvance = 0;          // 全零作业尾部 ESC(v（模式常量；0=不写）
    uint8_t dotSize = 0x21;        // ESC(e) 墨滴大小
    uint8_t method = 0x41;         // ESC(m) 打印方法
    QVector<int> colorCodes;       // 每块内记录顺序（ESC i 颜色码）
    QVector<int> recordOffsets;    // 每记录纵向偏移（page unit，物理头色行错位）
};

// modeId -> 实测参数表（A3-DTF-1390.prs，mode 0..3/5/7/9）
Escp2ModeParams escp2ModeParams(int modeId);

// 内容点阵：planes[record] = widthDots*heightDots 字节，值 0..3
//   widthDots  = content_w_dots（水平 DPI）
//   heightDots = content_h_units（page unit 行数）
struct Escp2PageRaster {
    int widthDots = 0;
    int heightDots = 0;
    QVector<QVector<uint8_t>> planes;   // 顺序 = 记录顺序（colorCodes）
};

// 布局计算结果（便于验证/报告）
struct Escp2LayoutInfo {
    int p0 = 0;             // 内容起点（page unit）
    int blockCount = 0;
    int advance = 0;
    int rowStep = 0;
    int bytesPerLine = 0;
    int widthDots = 0;      // content_w_dots
    int heightDots = 0;     // content_h_units
    int contentWUnits = 0;  // ESC(S) 宽（pageUnit 单位）
    QVector<int> positions; // pos[k]
};

// 只计算几何（不生成数据）
Escp2LayoutInfo computeEscp2Layout(const Escp2ModeParams &mp, int widthDots, int heightDots);

// 纸行 p -> (块 k, 行 r)；无解返回 false。pos0=initialAdvance。
bool escp2SolveBlockRow(const Escp2ModeParams &mp, int pos0, int p, int *block, int *row);

// 生成整份 .prn 内容（内存）
//   cfg 提供作业头信息（作业名/主机名/时间）；命令区参数由 mp 决定
bool buildEscp2Prn(const Escp2ModeParams &mp, const Escp2PageRaster &page,
                   const Escp2Config &cfg, QByteArray *out,
                   Escp2LayoutInfo *info, QString *err);

// 生成并写文件
bool writeEscp2Prn(const QString &prnPath, const Escp2ModeParams &mp,
                   const Escp2PageRaster &page, const Escp2Config &cfg,
                   Escp2LayoutInfo *info, QString *err);

// 页面点阵 -> 单色预览 QImage（不依赖 Qt 图像插件）
QImage escp2PlanePreview(const QVector<uint8_t> &plane, int width, int height);

// 校验平面数量/尺寸
bool normalizePageForMode(const Escp2ModeParams &mp, Escp2PageRaster *page, QString *err);

} // namespace mtr
